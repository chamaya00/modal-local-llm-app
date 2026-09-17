# modal-local-llm-app

A Modal-hosted Gradio chat UI serving Qwen2.5-14B-Instruct via vLLM on a
single L40S GPU, behind a shared passcode. See
[`docs/decisions/0001-model-and-gpu-selection.md`](docs/decisions/0001-model-and-gpu-selection.md)
for why this model and GPU tier, and
[`docs/design/3-chat-ui-flow.md`](docs/design/3-chat-ui-flow.md) for the
passcode gate, waking-up, and paused states.

## Setup

Install dependencies:

```
uv sync
```

Two Modal secrets must exist before `modal deploy` will serve real traffic -
creating them is a human step, not something this app does for itself:

```
modal secret create chat-passcode PASSCODE=<the shared passcode>
modal secret create app-paused APP_PAUSED=false
```

- `chat-passcode` / `PASSCODE` - the passcode visitors must enter at the
  Passcode Gate before any inference call is made.
- `app-paused` / `APP_PAUSED` - operator switch for the Paused state.
  Setting `APP_PAUSED=true` (case-insensitive) and letting the running
  container recycle (or running `modal app stop modal-local-llm-chat` to force
  it) takes the app offline behind a static message, checked before the
  passcode gate, to protect the monthly Modal credit. Set it back to `false`
  (or anything else) to resume.

The model (Qwen2.5-14B-Instruct) is Apache-2.0 and ungated, so no
HuggingFace token or secret is required to download its weights.

## Commands

- Install: `uv sync`
- Dev: `modal serve app.py`
- Deploy: `modal deploy app.py`
- Checks: `uv run ruff check .`, `uv run mypy .`, `uv run pytest`
