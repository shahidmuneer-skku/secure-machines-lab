"""The confidentiality filter for model-written text (owner, 2026-10-02)."""

from __future__ import annotations

import pytest

from sml.catalog.registry import registry
from sml.core.confidential import StreamGuard, mentions_method, scrub


@pytest.mark.parametrize(("text", "kept"), [
    ("The face looks pasted. Its EXIF data lists an AI tool as the software.", "The face looks pasted."),
    ("Our detectors agreed. The skin near the jaw is unusually smooth.", "The skin near the jaw is unusually smooth."),
    ("No C2PA content credentials were found. Shadows fall to the left.", "Shadows fall to the left."),
    ("이미지의 메타데이터에 AI 생성 흔적이 있습니다. 얼굴 경계가 부자연스럽습니다.", "얼굴 경계가 부자연스럽습니다."),
    ("Die Metadaten enthalten keine Hinweise. Die Beleuchtung wirkt natürlich.", "Die Beleuchtung wirkt natürlich."),
    ("- Face swap: likely manipulated (92%).\n- A face detection step ran first.",
     "- Face swap: likely manipulated (92%)."),
])
def test_sentences_about_the_method_are_dropped(text, kept):
    assert scrub(text) == kept


@pytest.mark.parametrize("text", [
    "The system checked if the face had been swapped with someone else's.",
    "The system checked for artifacts common in AI-generated images (like strange textures or lighting errors).",
    "Our analysis looks for signs of blending around the face.",
    "The model relies on subtle patterns.",
    "The AI-generation analysis examines the texture of the skin.",
    "The analysis specifically searches for inconsistencies.",
    "This analysis checks specifically for face-swapping and AI-generation artifacts.",
    "In this system, a score below 50% generally leans toward authentic.",
    "Anything above the threshold is marked as manipulated.",
    "판정 임계값은 공개되지 않습니다.",
    "Der Schwellenwert liegt bei 50 %.",
    "Because the probabilities here are relatively low (all below 50%), the system concludes it is real.",
    "Since both numbers are over 50 %, it leans towards manipulated.",
])
def test_speculation_about_what_the_analysis_looks_for_is_dropped(text):
    assert mentions_method(text)


@pytest.mark.parametrize("text", [
    "The analysis found no strong indicators of manipulation.",
    "The analysis indicates that this image is likely authentic.",
    "When the analysis finishes, you will see a verdict and a probability.",
    "You can look for unnatural blinking or mismatched lighting.",
    "Use reverse image search tools to check whether the image appeared earlier.",
    "Low quality, heavy compression or small faces make any analysis harder.",
    "I see a man wearing glasses in an office.",
    "The overall probability of manipulation is 42%.",
])
def test_outcomes_and_advice_are_kept(text):
    assert not mentions_method(text)


@pytest.mark.django_db
def test_every_detector_in_the_catalog_is_covered():
    for spec in registry().models.values():
        name = spec.display_name.get("en", spec.id)
        if name.lower() in {"center", "effort"}:
            continue
        assert mentions_method(f"The {name} result was high."), name


def test_everyday_words_that_are_also_detector_names_are_kept():
    text = "A llama stands in the center of the picture. It took some effort to see the edges."
    assert scrub(text) == text


def test_a_heading_without_anything_left_goes_too():
    text = "### Provenance\nNo C2PA manifest.\n### Caveats\nThe image is small."
    assert scrub(text) == "### Caveats\nThe image is small."
    bold = "**How it was checked**\nThe detectors compared the EXIF data.\n\n**Verdict:**\nLikely authentic."
    assert scrub(bold) == "**Verdict:**\nLikely authentic."


def test_streamed_answers_are_released_sentence_by_sentence():
    guard = StreamGuard()
    chunks = ["The face looks ", "smooth. The EXIF ", "data names Photoshop. Shadows", " fall left."]
    out = "".join(t for c in chunks for t in guard.feed(c)) + "".join(guard.flush())
    assert out == "The face looks smooth. Shadows fall left." and guard.dropped == 1
