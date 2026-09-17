"""Gradio UI: wires the pure state machine in `logic.py` onto components.

Component names match `docs/design/3-chat-ui-flow.md`'s "Components"
section: PasscodeGate, ChatPanel, StatusBanner, PausedScreen.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from typing import Any

import gradio as gr

from chatapp.logic import (
    ColdStartTracker,
    Session,
    handle_message,
    initial_screen,
    verify_passcode,
)


def _visibility(screen: str) -> tuple[Any, Any, Any]:
    """(paused, gate, chat) visibility updates for the given screen.

    PausedScreen never renders alongside PasscodeGate or ChatPanel -
    exactly one of the three is visible at a time.
    """
    return (
        gr.update(visible=screen == "paused"),
        gr.update(visible=screen == "gate"),
        gr.update(visible=screen == "chat"),
    )


def build_demo(
    generate_fn: Callable[[str, list[Any]], str],
    expected_passcode: str,
    paused_flag_fn: Callable[[], str],
    tracker: ColdStartTracker | None = None,
) -> gr.Blocks:
    """Build the chat UI.

    `paused_flag_fn` is a callable rather than a plain value so every
    check - page load and each message send - reads the operator
    switch fresh, matching the design's requirement that an
    already-open tab also sees the paused state once it's flipped.
    """
    tracker = tracker or ColdStartTracker()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    with gr.Blocks(title="Local LLM chat") as demo:
        session_state = gr.State(Session())

        with gr.Group(visible=False) as paused_screen:
            gr.Markdown(
                "This demo is paused to stay within its monthly compute "
                "budget. It'll be back after the credit resets."
            )

        with gr.Group(visible=True) as passcode_gate:
            passcode_input = gr.Textbox(label="Passcode", type="password")
            passcode_error = gr.Markdown("")
            passcode_submit = gr.Button("Enter")

        with gr.Group(visible=False) as chat_panel:
            chatbot = gr.Chatbot(type="messages", label="Chat")
            status_banner = gr.Markdown("")
            message_box = gr.Textbox(label="Message", interactive=True)
            send_button = gr.Button("Send")

        def on_load() -> tuple[Any, Any, Any]:
            return _visibility(initial_screen(paused_flag_fn()))

        demo.load(fn=on_load, inputs=None, outputs=[paused_screen, passcode_gate, chat_panel])

        def on_passcode_submit(submitted: str) -> tuple[Any, Any, Any, Session, str]:
            session, screen, error = verify_passcode(submitted, expected_passcode, paused_flag_fn())
            paused_u, gate_u, chat_u = _visibility(screen)
            return paused_u, gate_u, chat_u, session, error

        passcode_submit.click(
            fn=on_passcode_submit,
            inputs=[passcode_input],
            outputs=[paused_screen, passcode_gate, chat_panel, session_state, passcode_error],
        )

        def on_send(
            message: str, history: list[Any], session: Session
        ):
            for screen, status, response in handle_message(
                message, history, session, paused_flag_fn(), generate_fn, tracker, executor
            ):
                paused_u, gate_u, chat_u = _visibility(screen)
                new_history = history
                box_update = gr.update(interactive=False, value=message)
                if response is not None:
                    new_history = [
                        *history,
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": response},
                    ]
                    box_update = gr.update(interactive=True, value="")
                yield (
                    paused_u,
                    gate_u,
                    chat_u,
                    new_history,
                    status,
                    box_update,
                )

        send_button.click(
            fn=on_send,
            inputs=[message_box, chatbot, session_state],
            outputs=[paused_screen, passcode_gate, chat_panel, chatbot, status_banner, message_box],
        )
        message_box.submit(
            fn=on_send,
            inputs=[message_box, chatbot, session_state],
            outputs=[paused_screen, passcode_gate, chat_panel, chatbot, status_banner, message_box],
        )

    return demo
