# 0012 · Image studio: generation and editing with the admin's model

**Context.** The owner asked (2026-10-01) for an image generation and editing tool built on the latest
open Qwen-Image models, able to take several images and an instruction, with a UI that adapts to
different models and an administrator who chooses the model. FLUX.2 and HunyuanImage 3.0 were
candidates. The owner's decisions:

- *Models.* Qwen-Image-2512 (text → image) and Qwen-Image-Edit-2511 (up to 3 images + instruction),
  both Apache 2.0; FLUX.2 [klein] 4B (Apache 2.0, generate + multi-reference edit); Qwen-Image-2.1
  (unified, up to 10 references, transparency; Qwen Research License, non-commercial). The
  non-commercial model may be used with credits for now; a commercial license is to be bought before
  going live. FLUX.2 [dev] skipped for now (gated, non-commercial, 178 GB); HunyuanImage 3.0 excluded
  (its license does not cover the EU, the UK and South Korea).
- *Access.* Any signed-in user with credits (capability `use_studio`, module `studio`).
- *Price.* 3 credits per generated image, 2 per edited image (PriceRules `studio_generate`,
  `studio_edit`, admin-editable), charged only for images delivered.
- *Labelling.* None (plain PNG files).
- *Safeguards.* A consent confirmation when a reference image shows a face (logged with the job), and
  a content filter refusing sexual and violent requests and outputs.
- *Loading.* The model the admin picks stays loaded; other models load on demand and the admin's model
  is loaded again afterwards.

**Decision.**

- *Registry.* `config/studio.yaml` lists the models: diffusers pipeline, Hugging Face repository,
  modes, license, working memory, how the studio's controls map to the pipeline's arguments (`call`)
  and what is offered (`capabilities`: reference images, formats, steps, guidance, negative prompt,
  transparency, images per request). The API derives the controls per mode from it
  (`StudioModel.controls`), validates every request against them, and the web studio renders exactly
  those controls, so a new model needs a YAML entry, not code.
- *Admin choice.* `PlatformSettings.studio_generate_model` / `studio_edit_model` / `studio_enabled`
  (Admin → Studio). Users never see the model's name; staff with `manage_models` can try any installed
  model from the studio page (it loads on demand).
- *Studio server.* `sml_worker/studio/server.py` runs in its own conda env (`imagegen`: Python 3.12,
  PyTorch cu128 for the Blackwell GPU, diffusers from source) on GPU 1 (RTX PRO 6000), started and
  restarted by the resident supervisor. It keeps the admin's models loaded in order of preference
  within a memory budget (66 GB; Ollama and other services share the GPU), swaps a requested model in
  by evicting what does not fit, and restores the admin's models after 45 s idle. Requests that use the
  GPU run one at a time; a disconnected client cancels at the next denoising step; an out-of-memory
  error evicts the other models and retries once.
- *Jobs.* A studio request is a `Job(kind=studio)` with one `JobTask(kind=studio)` on queue
  `sml.studio`, so it shares the dispatcher, fair queueing, credit holds, history, live progress (SSE),
  cancellation and retention with detection. The hold is images × unit price; `finalize_studio`
  settles it for the images delivered (`credits.settle`). Outputs become the user's media
  (`MediaObject.generated_by`), so they can be downloaded, edited again or analysed by the detectors.
- *Safeguards.* The studio worker (`sml_worker/studio/task.py`) checks the prompt with the platform's
  local LLM (the reasoning model on Ollama; sexual content involving minors is refused by a pattern
  before the LLM) and fails closed when the LLM is unavailable; the server checks reference images and
  every output with the platform's NSFW classifier (transparent pixels flattened on white) and counts
  faces in references with SCRFD. Faces without consent → `CONSENT_REQUIRED`; the consent statement
  version, time, IP and user agent are stored in `Job.options.consent`, and a timeline event records it.
  Refused requests and withheld images are not charged.
- *History.* Studio jobs are left out of `GET /jobs` (detection results) unless `kind=studio` is asked
  for; the studio lists them at `GET /studio/jobs`.

**Consequences.** The two default Qwen models need about 54 GB each and cannot both stay loaded next to
Ollama on GPU 1: the generation model stays loaded and an edit swaps the edit model in (10–30 s from the
page cache), then the generation model returns. Choosing Qwen-Image-2.1 or FLUX.2 [klein] for both modes
avoids the swap. Generating at 2048 px with Qwen-Image-2.1 needs about 60 GB in total. The prompt check
adds about a second and depends on Ollama. Purging a studio job (retention or deletion) removes its
images and reference uploads unless another live job still uses them.
