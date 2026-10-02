# 0015 · How we detect stays confidential; a chat assistant explains results without it

**Context.** The owner decided (2026-10-02) that users must not be able to learn how Secure Machines
Lab detects manipulated or AI-generated media — not which detectors run (0011), and now also not
whether a file's metadata is read, which extra checks run or what they found. This applies to the
results page and the AI explanation, downloadable reports, the developer API, the homepage, pricing
and docs, the free trial, and a new chat assistant in which users discuss their images and videos
with the Ollama model the agents already use (`qwen3.6:27b`). This supersedes 0011's "metadata
evidence stays visible".

**Decision.**

- *Users see outcomes only.* `sml/jobs/public.py` gives the verdict label (e.g. "Likely
  AI-generated"), the overall probability, the result of each analysis (face swap, AI generation),
  the heatmaps the admin chose and a plain "no face found" note. Provenance (EXIF / XMP / C2PA,
  camera, software), check results (face detection, content safety, liveness), metadata-based verdict
  reasons and the "checks" step are gone from the user API, live events, reports (PDF / HWP / CSV /
  ZIP), the contract and the web app. Audit tasks still run and still vote; users see their progress
  as part of the generic "analysis" step, and timeline messages of older jobs that named a check are
  filtered out.
- *Prompts are built from that view.* The explanation, news and assistant prompts receive only what
  users see, and each carries a confidentiality rule. The assistant knows only verdicts and
  probabilities: it gives no reasons for a result, does not say what an analysis looks for and never
  compares a probability with a fixed percentage (the verdict threshold is an admin setting).
- *Model output is filtered as well.* `sml/core/confidential.py` drops every sentence that mentions
  the method — metadata and check terms in English, Korean and German, every catalogued detector
  name, thresholds and cut-offs, and sentences in which the system or analysis "checks for", "looks
  for" or "relies on" something — then removes headings left empty. It runs when explanations and
  news reports are stored and served, and on the assistant's replies sentence by sentence while they
  stream (`StreamGuard`) and again when stored and served. A reply with nothing left becomes a short
  note that the methods are confidential. The API log counts withheld sentences.
- *Staff-only content is decided on the server.* The admin layout asks the API who the user is
  (`serverMe`, with the browser's session cookie) and answers anyone who is not staff with a 404, so
  the console and its texts never reach them. The root layout sends every page all messages except
  the admin console's. On the results page the detector breakdown's texts are read on the server and
  sent to administrators only, and the card's code is loaded only in their browsers (`next/dynamic`).
- *The assistant is a separate full-page app* (`/assistant`, opened from the dashboard in a new tab;
  owner, 2026-10-02): conversations on the left, the chat on the right. Attached files become
  ordinary detection jobs at the normal price per file; chatting is free (owner). The model sees the
  images and may describe them, but never judges authenticity itself or contradicts the analysis
  (owner). Once every analysis a message started has finished, it explains the results unprompted,
  once per message (enforced with a row lock). "Ask the assistant" on a result starts a chat about it
  without analysing it again. It knows the current prices from `credits.pricing`. Replies are
  Server-Sent Events answering a POST (`Cache-Control: no-transform` so proxies do not compress and
  hold them back; keep-alive comments while the model is busy); Stop keeps what was said. Access
  needs the `use_assistant` capability (users have it) and the "assistant" module; 20 messages a
  minute per user (`THROTTLE_ASSISTANT`).

**Consequences.**

- Users learn from the product what each analysis concluded and how sure it is, never why or how.
  The admin console keeps the full detail (detector breakdown, EXIEF findings, check results, logs).
- The filter can drop an innocent sentence (a user asking about their photo's metadata gets an answer
  without it); a dropped sentence is preferred to a leak. Detector names that are everyday words
  ("Center", "Effort") are matched only in context. Speculation in Korean or German that names no
  term is left to the prompt.
- Ollama serves one request at a time, so a chat reply can wait behind an explanation or a news-agent
  step; both use the same context size, so the model is never reloaded between them.
- The staff check costs one request from the web server to the API per admin page and per result
  page. Next serves every built chunk as a public static file: the breakdown card's code (no texts)
  can still be found by someone reading the bundle runtime.
- `sml/jobs/tests/test_privacy.py`, `sml/core/tests/test_confidential.py` and
  `sml/assistant/tests` assert that no method term reaches users.
