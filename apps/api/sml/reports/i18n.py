"""Report strings (EN / KO / DE). Reports never name the detectors or describe how they work."""

LABELS = {
    "en": {
        "analysis_face_swap": "Face-swap analysis", "analysis_ai_generated": "AI-generation analysis",
        "ai_generated": "Likely AI-generated",
        "title": "Media Forensics Report", "subtitle": "Deepfake & AI-generated media analysis",
        "verdict": "Verdict", "fake": "Likely manipulated / AI-generated", "real": "Likely authentic",
        "no_face": "No face detected", "inconclusive": "Inconclusive", "probability": "Fake probability",
        "file": "File", "file_name": "File name", "type": "Type", "size": "Size", "resolution": "Resolution",
        "duration": "Duration", "sha256": "SHA-256", "submitted": "Submitted", "completed": "Completed",
        "job_id": "Job ID", "status": "Status",
        "xai": "Explainability", "explanation": "Reasoning (AI analyst)",
        "disclaimer": ("Scores are probabilistic estimates from automated analysis and may be wrong. This "
                       "report supports, but does not replace, expert review and must not be used as sole "
                       "legal evidence."),
        "generated": "Generated", "page": "Page", "run": "Run",
        "partial": "Some analysis steps could not complete; the verdict is based on the steps that finished.",
        "reasons": "Why",
        "timeline": "Processing timeline", "analysis": "Overall: the strongest finding across the analyses",
        "stopped_early": "The scan was stopped before the end of the selected range",
        "news_agent": "Verification of the story and its sources",
        "check_failed": "Could not be completed",
        "heatmap": "Heatmap", "original": "Original", "face": "Face", "video": "Annotated video",
    },
    "ko": {
        "analysis_face_swap": "얼굴 합성(페이스 스왑) 분석", "analysis_ai_generated": "AI 생성 분석",
        "ai_generated": "AI 생성 가능성 높음", "title": "미디어 포렌식 보고서",
        "subtitle": "딥페이크 및 AI 생성 미디어 분석", "verdict": "판정", "fake": "조작 또는 AI 생성 가능성 높음",
        "real": "원본일 가능성 높음", "no_face": "얼굴이 감지되지 않음", "inconclusive": "판단 불가",
        "probability": "가짜 확률", "file": "파일", "file_name": "파일명", "type": "유형", "size": "크기",
        "resolution": "해상도", "duration": "길이", "sha256": "SHA-256", "submitted": "제출", "completed": "완료",
        "job_id": "작업 ID", "status": "상태", "xai": "설명 가능성(XAI)",
        "explanation": "추론 분석(AI 분석가)",
        "disclaimer": ("점수는 자동 분석의 확률적 추정치이며 틀릴 수 있습니다. 본 보고서는 전문가 검토를 "
                       "보조하며 단독 법적 증거로 사용될 수 없습니다."),
        "generated": "생성 일시", "page": "페이지", "run": "실행",
        "partial": "일부 분석 단계를 완료하지 못했으며, 완료된 단계의 결과로 판정했습니다.",
        "reasons": "근거", "timeline": "처리 과정",
        "analysis": "종합: 분석 결과 중 가장 강한 판정",
        "stopped_early": "선택한 구간이 끝나기 전에 분석이 중지되었습니다", "news_agent": "기사 내용과 출처 검증",
        "check_failed": "완료하지 못함",
        "heatmap": "히트맵", "original": "원본",
        "face": "얼굴", "video": "분석 영상",
    },
    "de": {
        "analysis_face_swap": "Face-Swap-Analyse", "analysis_ai_generated": "KI-Generierungs-Analyse",
        "ai_generated": "Wahrscheinlich KI-generiert",
        "title": "Medienforensik-Bericht", "subtitle": "Analyse von Deepfakes und KI-generierten Medien",
        "verdict": "Ergebnis", "fake": "Wahrscheinlich manipuliert / KI-generiert", "real": "Wahrscheinlich echt",
        "no_face": "Kein Gesicht erkannt", "inconclusive": "Nicht eindeutig",
        "probability": "Fake-Wahrscheinlichkeit", "file": "Datei", "file_name": "Dateiname", "type": "Typ",
        "size": "Größe", "resolution": "Auflösung", "duration": "Dauer", "sha256": "SHA-256",
        "submitted": "Eingereicht", "completed": "Abgeschlossen", "job_id": "Auftrags-ID", "status": "Status",
        "xai": "Erklärbarkeit",
        "explanation": "Begründung (KI-Analyst)",
        "disclaimer": ("Die Werte sind probabilistische Schätzungen einer automatischen Analyse und können "
                       "falsch sein. Dieser Bericht unterstützt eine Expertenprüfung, ersetzt sie aber nicht "
                       "und darf nicht als alleiniges rechtliches Beweismittel verwendet werden."),
        "generated": "Erstellt", "page": "Seite", "run": "Durchlauf",
        "partial": ("Einige Analyseschritte konnten nicht abgeschlossen werden; das Ergebnis beruht auf den "
                    "abgeschlossenen Schritten."),
        "reasons": "Begründung",
        "timeline": "Verarbeitungsverlauf", "analysis": "Gesamt: das deutlichste Ergebnis der Analysen",
        "stopped_early": "Die Analyse wurde vor dem Ende des gewählten Bereichs gestoppt",
        "news_agent": "Prüfung der Meldung und ihrer Quellen",
        "check_failed": "Konnte nicht abgeschlossen werden", "heatmap": "Heatmap", "original": "Original",
        "face": "Gesicht",
        "video": "Analysiertes Video",
    },
}

def labels(locale: str) -> dict[str, str]:
    return LABELS.get(locale, LABELS["en"])
