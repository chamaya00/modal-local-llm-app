# Research: model and GPU tier for the Modal-hosted chat demo

Decision this research serves: which specific open-weight model (>8B
parameters) and which specific Modal GPU tier will serve chat via vLLM for an
occasional personal demo, staying inside the $30/month free credit, and does
the chosen model's weights require a HuggingFace access token - so issue #3
(engineering) does not discover the pairing mid-implementation.

## Constraints from the issue

- Model must be larger than 8B parameters (Llama-3.1-8B-Instruct itself does
  not qualify - it is exactly 8B).
- Served via vLLM, deployed as a single Modal app.
- Traffic pattern is an occasional personal demo, not sustained load.
- Monthly cost has to be estimated against Modal's $30/month free credit
  (Starter plan), using Modal's actual billing model: per-second billing while
  a container is running, plus a scaledown window that keeps it warm (and
  billed) after each request - not the GPU's raw $/hour figure on its own.

## Modal GPU tiers (verified)

Pulled directly from Modal's pricing page on 2026-09-17
([modal.com/pricing](https://modal.com/pricing)):

| GPU | VRAM | $/sec | $/hr (derived) |
|---|---|---|---|
| T4 | 16 GB | $0.000164 | ~$0.59 |
| L4 | 24 GB | $0.000222 | ~$0.80 |
| A10 | 24 GB | $0.000306 | ~$1.10 |
| L40S | 48 GB | $0.000542 | ~$1.95 |
| A100 40GB | 40 GB | $0.000583 | ~$2.10 |
| A100 80GB | 80 GB | $0.000694 | ~$2.50 |
| H100 SXM5 | 80 GB | $0.001097 | ~$3.95 |

Modal's own docs confirm per-second billing and that containers "remain idle
for a short period before shutting down" - the `scaledown_window` on the
function decorator, default 60s, configurable from 2 seconds to 20 minutes -
and that the container is billed for the whole idle window, not just active
request time
([modal.com/docs/guide/cold-start](https://modal.com/docs/guide/cold-start)).

## Model options considered

| Model | Params | License | Gated (HF token needed) | Fits requirement |
|---|---|---|---|---|
| Llama-3.1-8B-Instruct | 8B | Llama 3.1 Community | Yes | No - not over 8B |
| Mistral-Nemo-Instruct-2407 | 12B | Apache-2.0 | No | Yes |
| **Qwen2.5-14B-Instruct** | **14.7B** | **Apache-2.0** | **No** | **Yes** |
| Gemma-2-27B-it | 27B | Gemma license | Yes (verified on model page) | Yes, but gated |
| Llama-3.1-70B-Instruct | 70B | Llama 3.1 Community | Yes (verified on model page) | Yes, but gated and large |

Sources: [Qwen/Qwen2.5-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct)
(14.7B total parameters, Apache-2.0, publicly downloadable - no gated-access
banner on the model page),
[meta-llama/Llama-3.1-70B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct)
(gated - requires accepting the Llama 3.1 Community License on HuggingFace
before download),
[google/gemma-2-27b-it](https://huggingface.co/google/gemma-2-27b-it) (gated -
requires accepting Google's usage terms).

Qwen2.5-14B-Instruct and Mistral-Nemo-Instruct-2407 are both viable,
similarly-licensed, ungated options. Qwen2.5-14B-Instruct is the larger of the
two while still fitting comfortably on a single mid-tier GPU, and it is the
more widely documented model in Modal's and vLLM's own example deployments,
which lowers the risk of an undocumented compatibility issue for the
engineering child. That is the deciding factor between them - not a
capability gap.

## GPU sizing for Qwen2.5-14B-Instruct

14.7B parameters in BF16 is approximately 14.7B x 2 bytes = ~29.4 GB of weights
alone, before vLLM's KV cache and activation memory. That rules out T4 (16GB),
L4 (24GB), and A10 (24GB) - the weights alone don't fit. It leaves L40S
(48GB), A100 40GB (40GB), and A100 80GB (80GB) as viable.

- A100 40GB fits the weights but leaves only ~10GB for KV cache and
  activations after vLLM's default GPU-memory headroom, and costs more per
  hour than L40S ($2.10 vs $1.95).
- L40S gives ~18GB of headroom over the weights alone for the same purpose at
  a lower hourly rate.
- A100 80GB and H100 give far more headroom than a single-user occasional demo
  needs, at 25-100% more per hour.

L40S is the better fit: cheapest tier that comfortably fits the model with
working room, for a workload that is never going to serve concurrent users at
this scale.

## Cold start (inference, not verified against a real deployment)

Modal's own published numbers are for smaller models: a 7-8B model with
weights cached in a Modal Volume (avoiding a fresh HuggingFace download every
cold start) loads in roughly 10-30 seconds, and GPU memory snapshots can cut
that further for models in the 7B-13B range
([modal.com/docs/examples/gpu_snapshot](https://modal.com/docs/examples/gpu_snapshot)).
Modal has not published a measured number for a ~14B model on L40S without
snapshotting. Scaling the 7-8B figure roughly by weight size (14.7B is
~1.8-2x an 8B model) gives an inferred cold-start estimate of **45-90
seconds** for container start plus vLLM engine init plus weight load from a
Volume to GPU memory - this is an inference, not a measurement, and the ADR's
cost estimate uses the conservative (higher) end of it. The engineering child
should measure the real figure on first deployment and correct the ADR if it
is materially different.

## Recommendation

Serve **Qwen2.5-14B-Instruct** (14.7B parameters, Apache-2.0, ungated - no
HuggingFace access token required) via vLLM on a **Modal L40S** GPU.

**Strongest argument against:** cold start is inferred, not measured, and if
the real figure lands well above 90 seconds, a first-message "waking up"
experience needs stronger UI handling than a short spinner - which is already
flagged as a design concern on the parent objective (#1), not something this
research can resolve by picking a different GPU.

Full decision recorded in
[`docs/decisions/0001-model-and-gpu-selection.md`](../decisions/0001-model-and-gpu-selection.md).
