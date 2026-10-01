# Adding a detection model

Models are data, not code: an entry in `config/models.yaml` registers a detector, gives it its own
queue (`sml.model.<id>`), and tells the worker how to run it. Model code is never imported into the
platform; the worker runs your script as a subprocess from the model's own conda environment.
Users never choose or see detectors: the admin decides on **Admin → Models** which ones run on
every image and every video job (ADR 0011).

## Where things live

| What | Where (this server) | Setting |
| --- | --- | --- |
| Detector code and weights | `~/fakedetector/fakedetector/detection_models/<Name>/` | `MODELS_ROOT` in `.env` |
| Conda environments | `~/anaconda3/envs/<env>/` | `CONDA_ROOT` |
| Long-form video detectors | `~/fakedetector/long-video-processor/` | `LONG_VIDEO_ROOT` |
| Registry: how each detector runs | `config/models.yaml` | `MODELS_CONFIG_PATH` |
| Output parsers, run logic | `apps/worker/sml_worker/adapters/` (`parsers.py`, `subprocess_cli.py`) | — |
| Runtime choices (on/off per media, category, heatmap, weight) | Admin → Models (database overrides) | — |

## 1. Make the script runnable from the command line

The worker calls an argv list (never a shell string) with the model's conda Python, from a
working directory you choose. Your script must:

- take the input file path as an argument (any format the upload validator accepts: JPG, PNG, WebP,
  BMP, AVIF images; MP4, WebM, MOV, AVI, MKV, GIF videos);
- print a score in one of the formats the parsers understand (`apps/worker/sml_worker/adapters/parsers.py`):

  | Parser | Output it looks for |
  | --- | --- |
  | `standard` | `Fake Prob: 0.83` (or `83`), `Aggregated FAKE Prob: …`, or the last `real: … fake: …` pair |
  | `b2` | `Average Real Probability: …` and `Average Fake Probability: …` (tensor reprs are fine) |
  | `center` | `real: 12.5` / `fake: 87.5` percentages |
  | `safe_csv` | a CSV with a `prediction` column (`result_file`), else `prediction: …` on stdout |

  Values in [0, 1] are probabilities, values in (1, 100] or with a `%` sign are percentages;
- exit non-zero on failure. `CUDA out of memory` and "no kernel image is available" in stderr are
  recognised and reported as `GPU_OOM` / `GPU_UNSUPPORTED`; anything else is `RUNTIME_ERROR`
  (retried once);
- for face models, print one of `No faces detected`, `NO_FACE_DETECTED` or `얼굴을 찾지 못했습니다`
  when there is no face. That is a result ("no face"), not an error, and the user is not charged;
- optionally print `FACES_JSON:{"faces": [...]}` with face boxes, and write heatmaps or crops as
  `inference_images/<stem>*.png`, annotated videos as `detected/<stem>*.mp4`, per-frame scores as
  `inference_csv/<stem>.csv` (under the models root). They are uploaded and shown with the result
  automatically; a per-frame CSV also drives the live progress bar for videos.

  The per-frame CSV is `frame,real,fake,result,progress`: one row per frame (probabilities or
  percentages; leave `real`/`fake` empty for a frame without a face), `progress` in percent, and a
  final `Total result,<real>,<fake>,<real|fake>,100` row, used when stdout has no score. The total may
  hold frame counts instead (the share of fake frames is used), and `Total result,0,0,no_face,100`
  means no frame had a face. A `0,0.5,0.5,processing,0.0` placeholder row is ignored.
  `detection_models/XB-DFD/sml_infer.py` is a compact example of a wrapper that does all of this for
  images and videos.

Do not choose a GPU in code: the worker sets `CUDA_VISIBLE_DEVICES` (and
`CUDA_DEVICE_ORDER=PCI_BUS_ID`). The script runs with its conda environment activated
(`PATH`, `CONDA_PREFIX`, `CONDA_EXE`), so a nested `python` call uses the same environment. It
receives an allow-listed environment only: locale, home, CUDA, Hugging Face / Torch caches; never
the platform's database, broker, payment or email settings.

If an environment needs extra variables (for example a library path because it was copied from
another machine), declare them once for the environment instead of per model:

```yaml
conda_envs:
  mixture3:
    LD_LIBRARY_PATH: "{env_prefix}/lib"   # prepended; {env_prefix} = <CONDA_ROOT>/envs/mixture3
```

## 2. Add the registry entry

```yaml
models:
  - id: my-detector                 # lowercase; becomes queue sml.model.my-detector
    display_name: {en: My Detector, ko: 마이 디텍터, de: Mein Detektor}
    description:
      en: One line for operators (admin console only; users never see detectors).
      ko: 운영자용 한 줄 설명(관리 콘솔 전용, 사용자에게는 표시되지 않음).
      de: Eine Zeile für Betreiber (nur Admin-Konsole; Nutzer sehen keine Detektoren).
    family: deepfake                # result group users see: deepfake (face swap) | ai_generated
    face_required: true             # enables "no face" handling
    xai: gradcam                    # gradcam | attention | none (informational)
    default_selected: false         # runs on every job of each supported media type (until Admin → Models overrides it)
    show_heatmap: false             # users see this detector's heatmap (one image)
    trial: false                    # used for guest trial checks
    weight: 1.0                     # weight within its result group
    gpu_mem_mb: 6000                # GPU memory reserved before it starts, until its first run measures the real peak
    # variant_of: my-detector       # for separate deepfake / AI-generated weights of one model
    # fallbacks:
    #   on_no_face: center          # run another model when this one finds no face
    #   on_runtime_error: xception  # run another model when this one fails
    media:
      image:
        conda_env: my-env           # <CONDA_ROOT>/envs/my-env/bin/python
        cwd: "{models_root}"
        argv: ["{python}", "my_detector/infer.py", "--input", "{input}", "--stem", "{stem}"]
        parser: standard
        timeout_seconds: 300
      video:
        conda_env: my-env
        cwd: "{models_root}"
        argv: ["{python}", "my_detector/infer_video.py", "{input}", "{stem}"]
        parser: standard
        timeout_seconds: 1800
```

Only list the media types the model supports; it can only be switched on for those.
Placeholders available in `argv` and `cwd`: `{python}`, `{models_root}`, `{long_video_root}`,
`{input}`, `{input_dir}`, `{stem}`, `{workdir}`, `{media}`, `{page_type}`,
`{original_name_b64}`, `{interval}`. Other per-media keys: `result_file` (for `safe_csv`,
may use `{workdir}`) and `convert_webp_to_jpg: true` for scripts that cannot read WebP.

Price does not depend on the model (prices are per file, see ADR 0006), so nothing changes in
billing.

## 3. Deploy

1. Make the conda environment available under `CONDA_ROOT/envs/<name>` on every GPU host.
   While it is missing, the worker (with `SML_WORKER_SIMULATE=auto`) returns simulated scores
   that are flagged as simulated in the result; set `SML_WORKER_SIMULATE=0` in production.
2. Restart the Celery API worker and the model workers (the API itself re-reads `models.yaml`
   when the file changes). Workers started with `--detectors` or `--all` pick up the new queue
   automatically; a dedicated worker can be started with `--models my-detector`:

   ```bash
   sudo systemctl restart sml-celery 'sml-worker@*'
   ```

3. In **Admin → Models** check that the model is listed with its queue and consumers (workers).
   The same page decides, at runtime and without editing `models.yaml`: whether it runs on every
   image and every video job, its category (face swap / AI-generated — the result group users
   see), whether users see its heatmap, its weight, and the trial selection.

## 4. Verify

- Switch the new model on (and the others off) in **Admin → Models**, run one image and one video
  through **Detect**, and open the job in **Admin → Jobs**: each task has its live log (the button
  next to it), and failures show the exit code and the last lines of stderr there and in the worker
  log (`journalctl -u sml-worker@<gpu>`). Users only see generic steps.
- A parser test next to the existing ones (`apps/worker/tests/test_parsers.py`) with a real line
  of your script's output keeps future changes honest. `test_subprocess_adapter.py` shows how to
  run an adapter end to end with a stand-in script.

## Long-form video models and audit steps

`long_video_models` (interval scoring of long videos) and `audit_steps` (face detection, safety
and anti-spoofing checks that run alongside the models) use the same `conda_env` / `cwd` /
`argv` fields; see the existing entries at the end of `config/models.yaml`. The `metadata` audit
(EXIF / XMP / C2PA) is built in and always runs.
