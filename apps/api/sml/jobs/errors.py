"""User-facing texts for task error codes.

Workers report a code plus technical detail (exit codes, stderr, file paths). Only the code and
the fixed text below ever reach users; the detail is stored for staff (`error_detail`).
The web app shows a translated version of the same codes (messages: job.taskError.*).
"""

from __future__ import annotations

USER_MESSAGES: dict[str, str] = {
    "GPU_OOM": "The GPU ran out of memory while running this model.",
    "GPU_UNSUPPORTED": "This model is temporarily unavailable on the assigned hardware.",
    "TIMEOUT": "The model took too long and was stopped.",
    "WORKER_LOST": "The worker running this model stopped responding.",
    "QUEUE_TIMEOUT": "No worker picked this task up in time.",
    "RUNTIME_ERROR": "The model stopped with an error.",
    "PARSE_ERROR": "The model finished without producing a score.",
    "CONFIG_ERROR": "This model is not configured correctly.",
    "INFRA_ERROR": "A temporary system error occurred.",
    "AGENT_ERROR": "The AI agent could not complete the task.",
    "INVALID_MEDIA": "The file could not be read by this model.",
    # Image studio
    "PROMPT_BLOCKED": "This request was refused by the content filter (sexual or violent content).",
    "INPUT_BLOCKED": "A reference image was refused by the content filter.",
    "CONSENT_REQUIRED": "A reference image shows a person. Confirm that you have their consent and try again.",
    "OUTPUT_BLOCKED": "The result was withheld by the content filter.",
    "SAFETY_UNAVAILABLE": "The content filter is unavailable right now, so the request was not run.",
    "STUDIO_UNAVAILABLE": "The image studio is not available right now.",
    "MODEL_UNAVAILABLE": "The image model is not available right now.",
}
DEFAULT_MESSAGE = "The model could not analyze this file."


def user_message(code: str) -> str:
    return USER_MESSAGES.get(code, DEFAULT_MESSAGE)
