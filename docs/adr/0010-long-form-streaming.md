# 0010 · Long-form video is streamed to a GPU service, not uploaded and queued

**Context.** Long-form videos run to hours and gigabytes. The previous lab system (the
long-video processor's realtime app) streamed the file to a GPU service and showed per-interval
results live; its notes record that analysing browser-captured JPEG frames flipped verdicts, so
decoding happens on the server. The owner asked to keep that behaviour (2026-09-30): stream,
don't store; all four long-form detectors selectable; charge per minute actually analysed; a
dedicated A5000 (GPU 2).

**Decision.** `apps/stream` is a FastAPI WebSocket service that runs in the legacy `safe` conda
environment and imports the legacy engines unchanged (SKKU-AIGC in process; SKKU (BEYBI),
SKKU-P2 and SKKU-P3 as subprocesses). The browser first creates a session in Django, which
reserves credits for the selected range and returns a signed token fixing model, range and file
size. The browser then streams the file over the socket; the service writes it to a temporary
file, runs one scan at a time on its GPU (others see their queue position), streams interval
events back, and reports `started` / `intervals` / `finished` to an internal Django endpoint
authenticated with a shared key. Django records the scan as a normal job (history, timeline,
reports), keeps only a preview frame, and settles the hold per started minute analysed.

Superseded in part by ADR 0011: the administrator chooses the long-form detector, and the browser's
token names the session only (the service claims the paid parameters from the API once).

**Consequences.** Videos never reach media storage; verdicts match the legacy system. The
service scrubs its environment at start-up because the legacy engine passes its environment to
detector subprocesses. Abandoned sessions are refunded by a sweep (no upload within 60 min, or
no report for 20 min). Re-analysing a different range streams the file again. The upload-based
long-video job type remains available to API clients.
