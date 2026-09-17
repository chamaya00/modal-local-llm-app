# Chat UI flow: passcode gate, waking-up, and paused-for-credit states

Issue: #3 (child of #1)

## Scope

This spec covers what a visitor sees from opening the public Gradio URL
through sending a message and getting a response, plus the three states
called out in #1: the passcode gate, the vLLM cold-start wait, and the
screen shown if the app has been deliberately taken offline to protect
the monthly Modal credit.

It does not cover: which model or GPU tier is used (research child #2,
independent of this spec — the waking-up copy below is written to hold
regardless of the answer), or automatic usage-based throttling. Nothing
here proposes tracking spend and switching states automatically; the
"paused" state below is triggered by a human, deliberately, the way #1
describes it. Automatic credit tracking is a different, larger feature
and is out of scope for this issue.

## Happy path

1. **Visitor opens the public Gradio URL.** They land on the **Passcode
   Gate** state: a single passcode field and a submit button. No chat
   textbox is visible or interactive yet.
2. **Visitor enters the shared passcode and submits.** The submission is
   checked server-side (see "Passcode Gate" below). On success, the UI
   transitions to **Chat Ready**: the gate is replaced by the chat
   textbox, a send button, and an empty message list.
3. **Visitor types a message and sends it.** The textbox and send button
   become disabled and the UI enters **Thinking** (normal wait) or
   **Waking Up** (cold-start wait) — see below for which, and why it
   matters that they read differently.
4. **A response arrives.** It is appended to the message list, the
   textbox and send button re-enable, and the UI returns to **Chat
   Ready** for the next message.

## States

### Passcode Gate

- **Purpose:** block any inference call until a visitor has proven they
  know the shared passcode. This exists so a crawler or stray bot
  hitting the public link cannot burn Modal credit unattended.
- **What the visitor sees:** a passcode input and a submit button.
  Nothing else on the page — no chat textbox, no message list, not even
  disabled — because an element that exists in the DOM but is merely
  hidden or disabled client-side is not a gate, it is a suggestion.
- **The check must happen server-side.** The passcode is verified in the
  same Modal backend function path that would go on to call vLLM — not
  in Gradio-side JavaScript or a client-side conditional that hides the
  textbox. A client-only gate can be defeated by calling the underlying
  Gradio prediction endpoint directly with no passcode at all, which
  still forwards the message to the model and still burns credit. The
  gate has to sit in front of the inference call itself: no valid
  passcode on the request, no call to the model, full stop.
- **Incorrect passcode:** the field shows an inline error ("Incorrect
  passcode — try again.") and stays on the Passcode Gate state. The
  field clears or stays populated — engineer's call, not user-visible
  enough to matter — but the page never partially reveals the chat UI
  on a failed attempt.
- **Correct passcode:** transitions to Chat Ready. What exactly proves
  the passcode server-side (a per-session token, a re-check on every
  message, something else) is an implementation decision for the
  engineer, not a UI-flow decision — but whatever it is, it must reject
  an inference request that arrives without it, not merely decline to
  render a button for it.

### Chat Ready

- **Purpose:** the default state once gated, before or between messages.
- **What the visitor sees:** an enabled textbox, an enabled send button,
  and the running message list (empty on first entry).

### Thinking (normal response wait)

- **Trigger:** a message is sent while the model container is already
  warm (i.e., not the first request after an idle period).
- **What the visitor sees:** the textbox and send button disable, and a
  status line appears near the input — e.g. "Thinking…" — distinct in
  wording from the Waking Up state below, so a visitor can tell a normal
  wait from a cold start.
- **What clears it:** the response arrives and is appended to the
  message list; input re-enables.

### Waking Up (cold-start wait)

- **Trigger:** a message is sent and it triggers (or lands during) a
  vLLM cold start — the model has to load into GPU memory before it can
  generate anything. This is slow enough, for any model in the size
  range #1 targets (>8B parameters), to read as broken if the UI just
  sits on a generic spinner.
- **What the visitor sees:** a status line distinct from "Thinking…" —
  e.g. "Waking up the model — this can take up to a minute on a cold
  start." The exact ceiling is a placeholder; the engineer fills in a
  real figure once #2 lands, but the state itself, and the fact that its
  copy must name an approximate wait rather than stay silent, does not
  wait on that number.
- **If the wait runs well past the stated ceiling** (say, more than
  1.5x it) without a response, the status line updates to something
  like "Still waking up — this is taking longer than expected." rather
  than sitting on the original text indefinitely. This does not need to
  be a hard timeout that cancels the request — just an acknowledgement
  that the visitor is still looking at a live state, not a hung one.
- **What triggers it to clear:** the response arrives and is appended to
  the message list; input re-enables. Same clearing behaviour as
  Thinking — the two states differ in what they say while waiting, not
  in how they end.
- **How the UI knows to show this instead of Thinking:** left to the
  engineer's implementation (e.g. the backend can track whether this is
  the container's first inference call since starting, and pass that
  flag back before generation begins). The requirement this spec fixes
  is only that the two waits are visibly different to the visitor, not
  how the distinction is detected.

### Paused (deliberately offline to protect credit)

- **Why this exists:** the $30/month Modal credit resets monthly rather
  than stopping gracefully on its own. The mitigation #1 describes is a
  human deliberately taking the app offline before the credit runs out
  for the month, rather than letting requests fail mid-response once it
  does. This state is what a visitor sees when that has happened.
- **Trigger:** a human operator flips the app into a paused state (e.g.
  a Modal secret or environment variable such as `APP_PAUSED=true`,
  checked at request time) — not an automatic threshold the app
  computes for itself. Nothing in this spec proposes the app tracking
  its own spend; that is a separate, larger feature and out of scope
  here.
- **What the visitor sees:** the entire page — gate and chat alike — is
  replaced by a single static message, e.g. "This demo is paused to
  stay within its monthly compute budget. It'll be back after the
  credit resets." No passcode field, no textbox, nothing that implies a
  message could be sent. A visitor who knows the passcode should see
  the same paused message as one who does not — the pause is checked
  before the gate, not after it.
- **What clears it:** the operator flips the flag back; the next page
  load (or the next poll, if the UI is already open — see note below)
  shows the Passcode Gate again.
- **Note on an already-open tab:** if a visitor already has the page
  open when it's paused mid-session, the next message they try to send
  should surface the same paused message (as a response to that
  attempt) rather than silently failing or hanging — the backend check
  that flips the whole page for a fresh load is the same check that
  guards the inference call for an existing one.

## Components

Naming these once so the same nouns show up in the code.

- **PasscodeGate** — the passcode field and submit button. Owns nothing
  about the chat itself. Must never allow a request that reaches the
  model to skip its check.
- **ChatPanel** — the textbox, send button, and message list together.
  Only rendered once the Passcode Gate has succeeded and the app is not
  Paused.
- **StatusBanner** — a single-line status area near the input, used for
  both "Thinking…" and "Waking up…" text (and its longer-than-expected
  follow-up). One component, different copy, so the two states are
  visibly related but distinguishable — not two unrelated widgets.
- **PausedScreen** — the full-page replacement shown instead of
  PasscodeGate or ChatPanel when the app is paused. Renders on its own;
  never renders alongside the gate or the chat panel.

## What this spec does not decide

- Whether responses stream token-by-token or arrive as one block. Either
  is compatible with the Thinking/Waking Up states above — if streaming,
  the first token's arrival is what clears the status banner, same as a
  full response would.
- The exact copy ceiling ("up to a minute") and the longer-than-expected
  threshold are placeholders pending #2's cold-start measurements; the
  states and their triggers do not change once that number is known,
  only the numbers in the copy.
