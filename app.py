"""Modal entrypoint: `modal deploy app.py`.

Single Modal app: one GPU-backed class serves both the vLLM model and
the Gradio chat UI (mounted as an ASGI app), so the container that
loads the model into GPU memory is the same one Gradio's callbacks run
in - which is what lets `ColdStartTracker` know, in-process, whether a
given request is this container's first.

## Required Modal secrets (create before `modal deploy` serves real
## traffic - see the PR description for the exact commands)

- `chat-passcode`, key `PASSCODE` - the shared passcode visitors must
  enter at the Passcode Gate.
- `app-paused`, key `APP_PAUSED` - operator switch for the Paused
  state. `"true"` (case-insensitive) pauses the app; unset or any
  other value leaves it live.

Per ADR 0001 (docs/decisions/0001-model-and-gpu-selection.md), the
model (Qwen2.5-14B-Instruct) has ungated weights, so no HuggingFace
token is required.
"""

from __future__ import annotations

import os
import sys

import modal

MODEL_NAME = "Qwen/Qwen2.5-14B-Instruct"
GPU = "L40S"
SCALEDOWN_WINDOW = 300  # seconds; matches ADR 0001's cost estimate

PASSCODE_SECRET_NAME = "chat-passcode"
PASSCODE_SECRET_KEY = "PASSCODE"
PAUSED_SECRET_NAME = "app-paused"
PAUSED_SECRET_KEY = "APP_PAUSED"

MODEL_VOLUME_PATH = "/models"
SYSTEM_PROMPT = "You are a helpful assistant."

# `src/` holds the testable, framework-light package; add it to the path
# so this process (running `modal deploy` locally) can `import chatapp` -
# needed for add_local_python_source below to find it. This does NOT put
# chatapp inside the remote container; add_local_python_source does that.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

app = modal.App("modal-local-llm-chat")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm==0.6.3",
        "gradio==5.4.0",
        # gradio 5.4.0 needs fastapi>=0.115.2,<1.0; vllm 0.6.3 needs
        # fastapi>=0.107.0 (excluding 0.113.x/0.114.0) - 0.115.6 satisfies both.
        "fastapi==0.115.6",
        # vllm 0.6.3 only declares transformers>=4.45.0 with no upper
        # bound, so pip resolves whatever is newest at install time. A
        # transformers release far newer than vllm 0.6.3 was tested
        # against restructures how a model's rope_scaling config is
        # represented, which crashes vllm's older, stricter parsing
        # ("assert \"factor\" in rope_scaling") on load - pin to a
        # release from vllm 0.6.3's own era instead.
        "transformers==4.46.3",
    )
    # pip_install only pulls published packages - our own src/chatapp
    # package has to be added explicitly or the remote container never
    # sees it (modal deploy only auto-mounts app.py itself, not src/).
    # Local additions go last: cheapest layer to invalidate on a code change.
    .add_local_python_source("chatapp")
)

with image.imports():
    from vllm import LLM, SamplingParams

model_volume = modal.Volume.from_name("chat-model-weights", create_if_missing=True)


@app.cls(
    gpu=GPU,
    image=image,
    volumes={MODEL_VOLUME_PATH: model_volume},
    scaledown_window=SCALEDOWN_WINDOW,
    secrets=[
        modal.Secret.from_name(PASSCODE_SECRET_NAME),
        modal.Secret.from_name(PAUSED_SECRET_NAME),
    ],
)
class ChatServer:
    @modal.enter()
    def load_model(self) -> None:
        from chatapp.logic import ColdStartTracker

        self.llm = LLM(
            model=MODEL_NAME,
            download_dir=MODEL_VOLUME_PATH,
            gpu_memory_utilization=0.90,
        )
        self.tracker = ColdStartTracker()

    def generate(self, message: str, history: list[dict[str, str]]) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
        messages.append({"role": "user", "content": message})
        sampling_params = SamplingParams(temperature=0.7, max_tokens=1024)
        outputs = self.llm.chat(messages, sampling_params)
        return outputs[0].outputs[0].text

    @modal.asgi_app()
    def web(self):
        from fastapi import FastAPI
        from gradio.routes import mount_gradio_app

        from chatapp.ui import build_demo

        expected_passcode = os.environ[PASSCODE_SECRET_KEY]

        def paused_flag() -> str:
            # Re-read on every call (page load and every message) so
            # a fresh container started after the operator flips the
            # secret picks up the new value - see the PR description
            # for the limit this still has on an already-warm container.
            return os.environ.get(PAUSED_SECRET_KEY, "")

        demo = build_demo(
            generate_fn=self.generate,
            expected_passcode=expected_passcode,
            paused_flag_fn=paused_flag,
            tracker=self.tracker,
        ).queue()

        web_app = FastAPI()
        return mount_gradio_app(web_app, demo, path="/")
