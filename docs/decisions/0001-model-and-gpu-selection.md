# ADR 0001: Model and GPU tier for the chat demo

Date: 2026-09-17
Status: accepted

## Context

The demo (#1) needs one specific open-weight model and one specific Modal GPU
tier before the engineering child (#3) can start - picking either mid-build
risks discovering a cost or licensing problem after the vLLM serving code is
already written. Three constraints forced the decision: the model has to be
larger than 8B parameters, it has to be served via vLLM on a Modal GPU
function, and the whole thing has to stay inside the $30/month free compute
credit under an occasional-personal-demo traffic pattern, not sustained
traffic. ">8B" likely rules out a T4 (16GB VRAM), which the objective flagged
explicitly as a pairing that needed a real decision rather than an assumption.
Full comparison of models and GPU tiers is in
[`docs/research/2-model-and-gpu-selection.md`](../research/2-model-and-gpu-selection.md).

## Decision

We serve **Qwen2.5-14B-Instruct** (14.7B parameters, Apache-2.0 license) via
vLLM on a **Modal L40S** GPU (48GB VRAM, $0.000542/sec).

**Gated weights: No.** Qwen2.5-14B-Instruct is publicly downloadable from
HuggingFace under Apache-2.0 - no license click-through, no HuggingFace access
token is required to pull the weights. This removes a setup step the parent
objective flagged as a risk (gated weights needing a token accepted and
stored as a Modal secret before anything can download); the engineering child
does not need that step for this model.

14.7B parameters in BF16 is ~29.4GB of weights alone, which rules out T4, L4,
and A10 (all ≤24GB VRAM) before KV cache or activation memory is even
counted. L40S is the cheapest tier that fits the weights with real headroom
(~18GB free for KV cache and activations); A100 40GB fits but costs more per
hour with less headroom, and A100 80GB/H100 give more room than a
single-user demo needs at 25-100% more per hour. Full reasoning for both the
model and the GPU choice is in the research document linked above.

### Cost estimate

Modal bills per second only while a container is running, and a container
stays warm (and billed) for its `scaledown_window` after the last request -
so the estimate below is total container-alive time per demo session, not the
GPU's raw hourly rate.

Inputs:

- **GPU rate:** L40S, $0.000542/sec = **$1.9512/hr** (from Modal's pricing
  page, 2026-09-17).
- **Assumed scaledown window:** 300 seconds (5 minutes) - long enough that a
  back-and-forth conversation doesn't pay a fresh cold start on every message,
  short enough that an abandoned session doesn't idle-bill for long.
- **Assumed cold-start time:** 90 seconds - the conservative (higher) end of
  an inferred estimate for loading a ~14B model into GPU memory via vLLM, with
  weights cached in a Modal Volume rather than re-downloaded from HuggingFace
  each time. This is an inference scaled from Modal's published 10-30s figure
  for 7-8B models, not a measurement; see the research document for the
  reasoning. The engineering child should measure the real figure and correct
  this ADR if it differs materially.
- **Assumed request pattern:** occasional personal demo, not sustained
  traffic - 10 sessions per month, each session ~5 minutes (300 seconds) of
  active use (a handful of message/response exchanges).

Per-session billed time = cold start + active use + scaledown tail
= 90s + 300s + 300s = **690 seconds** (~11.5 minutes).

Monthly billed time = 10 sessions x 690s = 6,900 seconds = **1.917 hours**.

Monthly cost = 1.917 hours x $1.9512/hr = **~$3.74/month**.

That is about 12% of the $30/month free credit, leaving roughly 8x headroom
before the free credit is exhausted. Even a much heavier month - say 40
sessions (showing the demo to several people) - comes to 40 x 690s = 27,600s
= 7.67 hours x $1.9512/hr ≈ **$14.96/month**, still under the $30 credit.

## Consequences

- No HuggingFace token or Modal secret is needed to download the model
  weights, simplifying the engineering child's setup.
- A single L40S container comfortably fits the model with room for vLLM's KV
  cache, so the engineering child does not need to tune GPU memory
  utilization down or shard the model.
- The 90-second cold-start estimate is unverified; the UI needs a visible
  "waking up" state for the first message of a session (already flagged on
  the parent objective, #1), and the engineering child should record the
  measured cold-start time once deployed.
- 14.7B parameters is well short of frontier open-weight model quality - this
  trades some response quality for a model that fits a single mid-tier GPU at
  low cost, which matches "occasional personal demo," not a production
  chat product.
- If a future objective wants a larger or gated model, this ADR's GPU choice
  and cost estimate no longer hold and need to be revisited, not assumed to
  scale linearly.

## Alternatives rejected

- **Llama-3.1-8B-Instruct** - rejected: exactly 8B parameters, does not
  satisfy the ">8B" requirement.
- **Mistral-Nemo-Instruct-2407 (12B, Apache-2.0, ungated)** - rejected: a
  viable, similarly-licensed alternative, but Qwen2.5-14B-Instruct is larger
  while still fitting the same GPU tier, and is more widely documented in
  Modal's and vLLM's own example deployments, lowering integration risk for
  the engineering child. Not a capability gap - a tie-breaker.
- **Gemma-2-27B-it (27B)** - rejected: gated on HuggingFace, requiring license
  acceptance and a token before download, which the objective flagged as a
  setup risk to avoid where possible; also needs a larger, more expensive GPU
  tier than L40S.
- **Llama-3.1-70B-Instruct (70B)** - rejected: gated on HuggingFace requiring
  a token, and at 70B needs an A100-80GB or larger GPU tier, which raises
  both cold-start time and hourly cost well beyond what an occasional
  personal demo needs.
- **T4** - rejected: 16GB VRAM cannot hold any model over the 8B floor at
  BF16 with room for KV cache.
- **L4 / A10 (24GB)** - rejected: cannot hold Qwen2.5-14B-Instruct's ~29.4GB
  of BF16 weights.
- **A100 40GB** - rejected: fits the weights but costs more per hour than
  L40S ($2.10 vs $1.95) while leaving less headroom for KV cache.
- **A100 80GB / H100** - rejected: far more VRAM and cost than a single-user,
  low-traffic demo needs; 25-100% higher hourly rate than L40S for no
  benefit at this scale.
