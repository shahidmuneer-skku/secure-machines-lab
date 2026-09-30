"""Report strings (EN / KO / DE)."""

LABELS = {
    "en": {
        "title": "Media Forensics Report", "subtitle": "Deepfake & AI-generated media analysis",
        "verdict": "Verdict", "fake": "Likely manipulated / AI-generated", "real": "Likely authentic",
        "no_face": "No face detected", "inconclusive": "Inconclusive", "probability": "Fake probability",
        "file": "File", "file_name": "File name", "type": "Type", "size": "Size", "resolution": "Resolution",
        "duration": "Duration", "sha256": "SHA-256", "submitted": "Submitted", "completed": "Completed",
        "job_id": "Job ID", "models": "Model results", "model": "Model", "score": "Fake %", "status": "Status",
        "weight": "Weight", "provenance": "Metadata & provenance", "ai_indicators": "AI-generation indicators",
        "none_found": "No AI-generation indicators found in metadata.", "audit": "Audit steps",
        "xai": "Explainability", "explanation": "Reasoning (AI analyst)",
        "disclaimer": ("Scores are probabilistic estimates from machine-learning models and may be wrong. "
                       "This report supports, but does not replace, expert review and must not be used as "
                       "sole legal evidence."),
        "generated": "Generated", "page": "Page", "run": "Run", "partial": "Some models failed; the verdict uses the "
        "models that completed.", "reasons": "Why", "metadata_ai_indicator": "Metadata indicates AI generation",
        "model_consensus": "Weighted consensus of detection models", "timeline": "Processing timeline",
    },
    "ko": {
        "title": "미디어 포렌식 보고서", "subtitle": "딥페이크 및 AI 생성 미디어 분석",
        "verdict": "판정", "fake": "조작 또는 AI 생성 가능성 높음", "real": "원본일 가능성 높음",
        "no_face": "얼굴이 감지되지 않음", "inconclusive": "판단 불가", "probability": "가짜 확률",
        "file": "파일", "file_name": "파일명", "type": "유형", "size": "크기", "resolution": "해상도",
        "duration": "길이", "sha256": "SHA-256", "submitted": "제출", "completed": "완료",
        "job_id": "작업 ID", "models": "모델별 결과", "model": "모델", "score": "가짜 %", "status": "상태",
        "weight": "가중치", "provenance": "메타데이터 및 출처", "ai_indicators": "AI 생성 흔적",
        "none_found": "메타데이터에서 AI 생성 흔적이 발견되지 않았습니다.", "audit": "감사 단계",
        "xai": "설명 가능성(XAI)", "explanation": "추론 분석(AI 분석가)",
        "disclaimer": ("점수는 머신러닝 모델의 확률적 추정치이며 틀릴 수 있습니다. 본 보고서는 전문가 검토를 "
                       "보조하며 단독 법적 증거로 사용될 수 없습니다."),
        "generated": "생성 일시", "page": "페이지", "run": "실행",
        "partial": "일부 모델이 실패했으며, 완료된 모델로 판정했습니다.",
        "reasons": "근거", "metadata_ai_indicator": "메타데이터에 AI 생성 흔적이 있음",
        "model_consensus": "탐지 모델의 가중 합의", "timeline": "처리 과정",
    },
    "de": {
        "title": "Medienforensik-Bericht", "subtitle": "Analyse von Deepfakes und KI-generierten Medien",
        "verdict": "Ergebnis", "fake": "Wahrscheinlich manipuliert / KI-generiert", "real": "Wahrscheinlich echt",
        "no_face": "Kein Gesicht erkannt", "inconclusive": "Nicht eindeutig", "probability": "Fake-Wahrscheinlichkeit",
        "file": "Datei", "file_name": "Dateiname", "type": "Typ", "size": "Größe", "resolution": "Auflösung",
        "duration": "Dauer", "sha256": "SHA-256", "submitted": "Eingereicht", "completed": "Abgeschlossen",
        "job_id": "Auftrags-ID", "models": "Modellergebnisse", "model": "Modell", "score": "Fake %",
        "status": "Status", "weight": "Gewicht", "provenance": "Metadaten & Herkunft",
        "ai_indicators": "Hinweise auf KI-Generierung",
        "none_found": "Keine Hinweise auf KI-Generierung in den Metadaten gefunden.", "audit": "Prüfschritte",
        "xai": "Erklärbarkeit", "explanation": "Begründung (KI-Analyst)",
        "disclaimer": ("Die Werte sind probabilistische Schätzungen von ML-Modellen und können falsch sein. "
                       "Dieser Bericht unterstützt eine Expertenprüfung, ersetzt sie aber nicht und darf nicht als "
                       "alleiniges rechtliches Beweismittel verwendet werden."),
        "generated": "Erstellt", "page": "Seite", "run": "Durchlauf",
        "partial": "Einige Modelle sind fehlgeschlagen; das Ergebnis basiert auf den abgeschlossenen Modellen.",
        "reasons": "Begründung", "metadata_ai_indicator": "Metadaten deuten auf KI-Generierung hin",
        "model_consensus": "Gewichteter Konsens der Erkennungsmodelle", "timeline": "Verarbeitungsverlauf",
    },
}


def labels(locale: str) -> dict[str, str]:
    return LABELS.get(locale, LABELS["en"])
