#!/usr/bin/env bash
#
# Creates the two Modal secrets this app needs and runs `modal deploy`,
# meant to run when this repo is opened in a GitHub Codespace (see
# .devcontainer/devcontainer.json's postAttachCommand). Safe to re-run -
# secret creation and deploy are both idempotent.
#
# Reads pre-seeded values from Codespaces secrets (environment variables
# GitHub injects automatically into the codespace) rather than asking you
# to type them in every time:
#
#   MODAL_TOKEN_ID / MODAL_TOKEN_SECRET - your Modal API credentials,
#     from https://modal.com/settings/tokens. Without these there's
#     nothing to authenticate `modal deploy` with, and this script exits
#     with instructions to run `uv run modal setup` by hand instead.
#   CHAT_PASSCODE - the shared passcode for the chat-passcode/PASSCODE
#     secret. If unset, you're prompted once for it (hidden input).
#
# Set these at https://github.com/settings/codespaces (or this repo's own
# Codespaces secrets page under Settings), grant this repository access,
# then rebuild/reopen the Codespace so they're injected.
#
# All output, including the deployed URL, is appended to
# codespaces-deploy-output.txt at the repo root - open it in the editor
# to copy anything you need. It's gitignored. The passcode value itself
# is never written to it.

set -uo pipefail  # not -e: several steps have their own fallback path

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OUTPUT_FILE="$REPO_ROOT/codespaces-deploy-output.txt"

log() {
  echo "$@" | tee -a "$OUTPUT_FILE"
}

run_logged() {
  # Runs a command, showing output live and appending it to the file.
  "$@" 2>&1 | tee -a "$OUTPUT_FILE"
  return "${PIPESTATUS[0]}"
}

{
  echo "=================================================================="
  echo "Modal setup + deploy run: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "=================================================================="
} >>"$OUTPUT_FILE"

if [ -z "${CODESPACES:-}" ]; then
  log "Note: \$CODESPACES is not set - this doesn't look like a GitHub Codespace."
  log "Continuing anyway, but the 'preseed via Codespaces secrets' story only applies inside one."
fi

# Degrade to instructions rather than hanging or silently doing nothing
# if this ever runs somewhere without a real terminal attached.
if [ ! -t 0 ]; then
  log "No interactive terminal - skipping the confirmation prompt."
  log "Run this yourself when ready: bash scripts/codespaces-deploy.sh"
  exit 0
fi

read -r -p "Create Modal secrets and run 'modal deploy app.py' now? [y/N] " answer
case "$answer" in
[yY][eE][sS] | [yY]) ;;
*)
  log "Skipped - not confirmed. Run 'bash scripts/codespaces-deploy.sh' any time you're ready."
  exit 0
  ;;
esac

log ""
log "Starting: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

if ! command -v uv >/dev/null 2>&1; then
  log "uv is not installed - installing it..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

log "Syncing dependencies (uv sync)..."
if ! run_logged uv sync; then
  log "uv sync failed - see output above. Aborting."
  exit 1
fi

# --- authenticate ---------------------------------------------------------
if [ -n "${MODAL_TOKEN_ID:-}" ] && [ -n "${MODAL_TOKEN_SECRET:-}" ]; then
  log "Authenticating to Modal from MODAL_TOKEN_ID/MODAL_TOKEN_SECRET (Codespaces secrets)..."
  if ! run_logged uv run modal token set --token-id "$MODAL_TOKEN_ID" --token-secret "$MODAL_TOKEN_SECRET"; then
    log "Could not authenticate with the provided token - see output above. Aborting."
    exit 1
  fi
else
  log "MODAL_TOKEN_ID/MODAL_TOKEN_SECRET are not set as Codespaces secrets."
  log "Set them at https://github.com/settings/codespaces (values from https://modal.com/settings/tokens),"
  log "grant this repo access, and reopen the Codespace - or run 'uv run modal setup' yourself now."
  exit 1
fi

# --- passcode ---------------------------------------------------------------
if [ -n "${CHAT_PASSCODE:-}" ]; then
  log "Using CHAT_PASSCODE from Codespaces secrets."
  passcode="$CHAT_PASSCODE"
else
  log "CHAT_PASSCODE is not set as a Codespaces secret - prompting instead."
  read -r -s -p "Enter the shared passcode to use for this deploy: " passcode
  echo
fi

if [ -z "$passcode" ]; then
  log "No passcode entered - aborting without creating secrets or deploying."
  exit 1
fi

# --- secrets ------------------------------------------------------------
# --force makes this safe to re-run: overwrites rather than erroring if
# the secret already exists.
log ""
log "Creating Modal secrets (chat-passcode, app-paused)..."
if ! run_logged uv run modal secret create chat-passcode "PASSCODE=$passcode" --force; then
  log "Failed to create chat-passcode - see output above. Aborting."
  exit 1
fi
if ! run_logged uv run modal secret create app-paused "APP_PAUSED=false" --force; then
  log "Failed to create app-paused - see output above. Aborting."
  exit 1
fi
log "Secrets created (the passcode value itself is not written to this file)."

# --- deploy ------------------------------------------------------------
log ""
log "Running: modal deploy app.py"
log "(first deploy downloads ~29GB of model weights into a Modal Volume - this can take several minutes)"
if run_logged uv run modal deploy app.py; then
  log ""
  log "Deploy succeeded - see the URL in the output above (also saved in $OUTPUT_FILE)."
else
  log ""
  log "Deploy failed - see the output above in $OUTPUT_FILE for the error."
  exit 1
fi

log ""
log "Done: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
log "Full output saved to: $OUTPUT_FILE"
