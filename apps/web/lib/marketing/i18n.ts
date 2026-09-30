export const SUPPORTED_LANGUAGES = [
  { code: "en", label: "EN", nativeName: "English", htmlLang: "en" },
  { code: "ko", label: "KO", nativeName: "한국어", htmlLang: "ko" },
  { code: "de", label: "DE", nativeName: "Deutsch", htmlLang: "de" },
] as const

export type Language = (typeof SUPPORTED_LANGUAGES)[number]["code"]

const en = {
  nav: {
    systems: "Systems",
    research: "Research",
    about: "About",
    customers: "Collaborators",
    contact: "Contact",
    getInTouch: "Get in touch →",
    language: "Select language",
  },
  hero: {
    status: "Systems operational",
    title: {
      secure: "SECURE",
      machines: "MACHINES",
      lab: "LAB.",
    },
    subtitle:
      "We build the detection layer for the generative era. Model- and data-free deepfake forensics, watermarking defenses, and tools to trace synthetic media as it spreads.",
    affiliation: "DASH Lab · SKKU",
    exploreSystems: "Explore the systems ↓",
    marquee: [
      "Deepfake detection",
      "Model-free forensics",
      "Generation source blocking",
      "Propagation prediction",
      "AI forensics assistant",
      "Synthetic watermarking",
      "Media provenance",
      "Adversarial robustness",
    ],
    stats: [
      { v: "99.4%", l: "Detection AUROC", sub: "CVPR’24 bench" },
      { v: "<120ms", l: "Analysis latency", sub: "per frame @ 1080p" },
      { v: "14", l: "Peer-reviewed publications", sub: "since 2023" },
      { v: "∞", l: "Synthetic samples analyzed", sub: "and counting" },
    ],
  },
  tools: {
    face: {
      eyeTitle: "EYE_L · 98.7%",
      eyeSub: "SYNTHETIC MARKER",
      noseTitle: "NOSE · CLEAN",
      noseSub: "FREQ ANALYSIS OK",
      browTitle: "BROW · 94.2%",
      browSub: "MICRO-EDGE DRIFT",
      mouthTitle: "MOUTH · ANOMALY",
      mouthSub: "DIFFUSION ARTIFACT",
      footer: "SML/FACE-V4 · 68 LANDMARKS · FRAME 00482",
    },
    sectionIdx: "02 / Systems",
    eyebrow: "Products",
    titleLine: "Safer AI.",
    titleEm: "Secure world.",
    subtitle:
      "Pioneering forensic tools for researchers, newsrooms, and platform trust teams. Our systems run landmark, frequency, and mesh-level analysis in real time — click through to launch the live terminal.",
    labels: {
      live: "Live",
      openLivePreview: "Open live preview",
      openFullSystem: "Open full system",
    },
    cards: {
      detector: {
        title: "Deepfake Detector",
        kicker: "Forensic analysis",
        desc:
          "A model-agnostic pipeline for spotting AI-generated and manipulated images and video. Trained on 2M+ synthetic samples across 40+ generators.",
        launch: "Launch Deepfake",
        metrics: [
          { k: "AUROC", v: "99.4%" },
          { k: "Latency", v: "118ms" },
          { k: "Models covered", v: "40+" },
        ],
      },
      assistant: {
        title: "Forensics Assistant",
        kicker: "Research copilot",
        desc:
          "A conversational agent for media integrity analysts — upload, cross-check, cite. Backed by our detection stack and an evolving evidence graph.",
        launch: "Launch Forensics",
        metrics: [
          { k: "Evidence sources", v: "12.4k" },
          { k: "Response time", v: "1.2s" },
          { k: "Languages", v: "8" },
        ],
      },
    },
    useCases: {
      eyebrow: "In the field",
      items: [
        { h: "Newsrooms", b: "Verify user-submitted footage before publish." },
        { h: "Platforms", b: "Flag synthetic uploads at scale, at the edge." },
        { h: "Researchers", b: "Benchmark new detection methods against ours." },
        { h: "Policy", b: "Audit evidence for investigations and regulation." },
      ],
    },
  },
  research: {
    idx: "03 / Research",
    eyebrow: "What we study",
    titleMain: "Core",
    titleEm: "Research.",
    subtitle:
      "Pioneering the next generation of AI security through foundational research and practical forensic implementation. Three parallel threads — detect, prevent, predict.",
    areas: [
      {
        tag: "DASH · CORE · STABLE",
        title: "Deepfake detection & AI forensics",
        desc:
          "Advanced forensics for identifying deepfakes and manipulated content without requiring extensive training datasets or prior knowledge of the generative model.",
        venues: ["CVPR ’25", "NeurIPS ’24"],
      },
      {
        tag: "SML · ALPHA · ACTIVE",
        title: "Generation source blocking",
        desc:
          "Implementing architectural safeguards within AI models to prevent the creation of deepfakes at the foundational level — making the synthetic visibly synthetic, at the source.",
        venues: ["ICML ’25", "USENIX Sec."],
      },
      {
        tag: "NODAL · BETA · MONITORING",
        title: "Propagation prediction",
        desc:
          "Heuristic AI models designed to track, analyze, and predict the viral spread of synthetic content across digital networks. Intervene before the cascade.",
        venues: ["WWW ’25", "KDD ’24"],
      },
    ],
    publications: {
      eyebrow: "Selected publications",
      title: "Recent work",
      all: "All publications →",
      tags: {
        full: "Full",
        datasets: "Datasets",
        workshop: "Workshop",
      },
    },
  },
  about: {
    idx: "04 / About",
    eyebrow: "About the lab",
    headingPrefix: "Born from DASH Lab at",
    university: "Sungkyunkwan University",
    headingSuffix: "grown into a company that ships forensic infrastructure.",
    body:
      "We're researchers first. We write the papers, build the benchmarks, and then harden the best ideas into production systems that newsrooms, platforms, and policymakers actually deploy. Our thesis: generative AI is here to stay — so the web needs a trust layer that moves at the same speed.",
    facts: [
      ["Founded", "2024"],
      ["HQ", "Suwon, KR"],
      ["Affiliation", "SKKU · DASH Lab"],
      ["Team", "12 researchers"],
      ["Funded by", "NRF, MSIT, angels"],
      ["Hiring", "Open (ML, infra)"],
    ],
  },
  customers: {
    idx: "05",
    eyebrow: "Collaborating organizations",
    title: "Collaborators",
    subtitle: "Organizations we are collaborating with to make online information more trustworthy.",
  },
  contact: {
    idx: "06 / Contact",
    titleLine: "Let's make",
    titleEm: "online information honest",
    titleEnd: "again.",
    subtitle:
      "Researchers, trust teams, newsrooms, policymakers — if you're working on synthetic media from any angle, we want to hear from you.",
    writeToUs: "Write to us",
    readLabNotes: "Read the lab notes",
    copy: "COPY",
    copied: "COPIED ✓",
    contacts: [
      {
        k: "General",
        v: "woo@securemachineslab.com",
        copyKey: "g",
        note: "Partnerships, press, platform integrations",
      },
    ],
    hq: "HQ",
    location: "Suwon-si, Gyeonggi-do",
    address: "Sungkyunkwan University · DASH Lab · South Korea",
    footer: {
      privacy: "Privacy",
      terms: "Terms",
      security: "Security",
      github: "GitHub ↗",
      status: "All systems operational",
    },
  },
  visitors: {
    idx: "07 / Visitors",
    eyebrow: "Live reach",
    title: "Where visitors are from",
    subtitle: "A live map of recent visits to Secure Machines Lab from around the world.",
  },
}

export type DashTranslations = typeof en

export const dashTranslations = {
  en,
  ko: {
    nav: {
      systems: "Systems",
      research: "Research",
      about: "About",
      customers: "Collaborators",
      contact: "Contact",
      getInTouch: "Get in touch →",
      language: "Select language",
    },
    hero: {
      status: "시스템 운영",
      title: en.hero.title,
      subtitle:
        "생성형 AI 시대의 탐지 솔루션을 구축합니다. 모델과 데이터에 의존하지 않는 딥페이크 포렌식, 워터마킹 방어, 합성 미디어 확산 추적 도구를 제공합니다.",
      affiliation: "DASH Lab · SKKU",
      exploreSystems: "시스템 살펴보기 ↓",
      marquee: [
        "딥페이크 탐지",
        "Model-free 포렌식",
        "생성 출처 차단",
        "확산 예측",
        "AI 포렌식 어시스턴트",
        "합성 워터마킹",
        "미디어 출처 증명",
        "적대적 강건성",
      ],
      stats: [
        { v: "99.4%", l: "탐지 AUROC", sub: "CVPR’24 벤치마크" },
        { v: "<120ms", l: "분석 지연시간", sub: "1080p 프레임당" },
        { v: "14", l: "동료심사 논문", sub: "2023년 이후" },
        { v: "∞", l: "분석한 합성 샘플", sub: "계속 증가 중" },
      ],
    },
    tools: {
      face: {
        eyeTitle: "EYE_L · 98.7%",
        eyeSub: "합성 마커",
        noseTitle: "NOSE · 정상",
        noseSub: "주파수 분석 정상",
        browTitle: "BROW · 94.2%",
        browSub: "미세 엣지 드리프트",
        mouthTitle: "MOUTH · 이상",
        mouthSub: "확산 아티팩트",
        footer: "SML/FACE-V4 · 68 랜드마크 · 프레임 00482",
      },
      sectionIdx: "02 / 시스템",
      eyebrow: "제품",
      titleLine: "Safer AI.",
      titleEm: "Secure World.",
      subtitle:
        "연구자, 뉴스룸, 플랫폼 신뢰팀을 위한 포렌식 도구를 개척합니다. 당사의 시스템은 랜드마크, 주파수, mash 수준 분석을 실시간으로 실행하며, 클릭하면 라이브 터미널을 실행할 수 있습니다.",
      labels: {
        live: "실시간",
        openLivePreview: "라이브 미리보기 열기",
        openFullSystem: "전체 시스템 열기",
      },
      cards: {
        detector: {
          title: "딥페이크 탐지기",
          kicker: "포렌식 분석",
          desc:
            "AI 생성 및 조작 이미지와 영상을 탐지하는 파이프라인입니다. 40개 이상의 생성 모델에서 나온 200만 개 이상의 합성 샘플로 학습했습니다.",
          launch: "딥페이크 탐지 실행",
          metrics: [
            { k: "AUROC", v: "99.4%" },
            { k: "지연시간", v: "118ms" },
            { k: "지원 모델", v: "40+" },
          ],
        },
        assistant: {
          title: "포렌식 어시스턴트",
          kicker: "연구 코파일럿",
          desc:
            "미디어 무결성 분석가를 위한 대화형 에이전트입니다. 업로드, 교차 검증, 인용을 지원하며 탐지 스택과 진화하는 증거 그래프를 기반으로 동작합니다.",
          launch: "포렌식 실행",
          metrics: [
            { k: "증거 소스", v: "12.4k" },
            { k: "응답 시간", v: "1.2s" },
            { k: "언어", v: "8" },
          ],
        },
      },
      useCases: {
        eyebrow: "현장 활용",
        items: [
          { h: "뉴스룸", b: "게시 전 사용자 제보 영상을 검증합니다." },
          { h: "플랫폼", b: "엣지에서 대규모 합성 업로드를 표시합니다." },
          { h: "연구자", b: "새 탐지 방법을 당사 시스템과 비교 벤치마크합니다." },
          { h: "정책", b: "수사와 규제를 위한 증거를 감사합니다." },
        ],
      },
    },
    research: {
      idx: "03 / 연구",
      eyebrow: "연구 주제",
      titleMain: "Core",
      titleEm: "Research.",
      subtitle:
        "기초 연구와 실용적인 포렌식 구현을 통해 차세대 AI 보안을 개척합니다. 탐지, 예방, 예측이라는 세 가지 흐름을 동시에 연구합니다.",
      areas: [
        {
          tag: "DASH · CORE · STABLE",
          title: "딥페이크 탐지 및 AI 포렌식",
          desc:
            "대규모 학습 데이터나 생성 모델에 대한 사전 지식 없이 딥페이크와 조작 콘텐츠를 식별하는 고급 포렌식 기술입니다.",
          venues: ["CVPR ’25", "NeurIPS ’24"],
        },
        {
          tag: "SML · ALPHA · ACTIVE",
          title: "생성 출처 차단",
          desc:
            "AI 모델 내부에 구조적 안전장치를 구현해 딥페이크 생성을 근본 단계에서 억제하고, 합성 콘텐츠가 출처에서부터 합성임을 드러내도록 합니다.",
          venues: ["ICML ’25", "USENIX Sec."],
        },
        {
          tag: "NODAL · BETA · MONITORING",
          title: "확산 예측",
          desc:
            "디지털 네트워크 전반에서 합성 콘텐츠의 바이럴 확산을 추적, 분석, 예측하는 휴리스틱 AI 모델입니다. 확산이 커지기 전에 개입합니다.",
          venues: ["WWW ’25", "KDD ’24"],
        },
      ],
      publications: {
        eyebrow: "선정 논문",
        title: "최근 연구",
        all: "전체 논문 →",
        tags: {
          full: "full",
          datasets: "datasets",
          workshop: "workshop",
        },
      },
    },
    about: {
      idx: "04 / 연구실 소개",
      eyebrow: "연구실 소개",
      headingPrefix: "성균관대학교",
      university: "DASH Lab",
      headingSuffix: "에서 시작해 포렌식 인프라를 제공하는 기업으로 성장했습니다.",
      body:
        "우리는 연구자입니다. 논문을 쓰고, 벤치마크를 만들며, 가장 좋은 아이디어를 뉴스룸, 플랫폼, 정책 담당자가 실제로 배포할 수 있는 프로덕션 시스템으로 강화합니다. 우리의 관점은 명확합니다. 생성형 AI는 이미 일상이 되었고, 웹에는 그 속도에 맞춰 움직이는 신뢰 계층이 필요합니다.",
      facts: [
        ["설립", "2024"],
        ["본사", "수원, KR"],
        ["소속", "SKKU · DASH Lab"],
        ["팀", "연구자 12명"],
        ["지원", "NRF, MSIT, 엔젤 투자"],
        ["채용", "진행 중 (ML, 인프라)"],
      ],
    },
    customers: {
      idx: "",
      eyebrow: "협력기관",
      title: "Collaborators",
      subtitle: "더 신뢰할 수 있는 온라인 정보 환경을\n함께 만들어 가는 협력 기관입니다.",
    },
    contact: {
      idx: "06 / 연락처",
      titleLine: "Let's make",
      titleEm: "online information honest",
      titleEnd: "again.",
      subtitle:
        "연구자, 신뢰팀, 뉴스룸, 정책 담당자 등 합성 미디어를 다루는 모든 분들의 연락을 기다립니다.",
      writeToUs: "메일 보내기",
      readLabNotes: "랩 노트 읽기",
      copy: "복사",
      copied: "복사됨 ✓",
      contacts: [
        {
          k: "일반 문의",
          v: "woo@securemachineslab.com",
          copyKey: "g",
          note: "파트너십, 언론, 플랫폼 연동 문의",
        },
      ],
      hq: "본사",
      location: "경기도 수원시",
      address: "성균관대학교 · DASH Lab · 대한민국",
      footer: {
        privacy: "개인정보",
        terms: "이용약관",
        security: "보안",
        github: "GitHub ↗",
        status: "전체 시스템 정상 운영",
      },
    },
    visitors: {
      idx: "07 / 방문자",
      eyebrow: "실시간 도달",
      title: "방문자 통계",
      subtitle: "전 세계에서 Secure Machines Lab을 찾아온 최근 방문의 실시간 지도입니다.",
    },
  },
  de: {
    nav: {
      systems: "Systems",
      research: "Research",
      about: "About",
      customers: "Collaborators",
      contact: "Contact",
      getInTouch: "Get in touch →",
      language: "Select language",
    },
    hero: {
      status: "Systeme betriebsbereit",
      title: en.hero.title,
      subtitle:
        "Wir bauen die Erkennungsebene für das Zeitalter generativer KI: modell- und datenfreie Deepfake-Forensik, Watermarking-Abwehr und Werkzeuge, die synthetische Medien bei ihrer Verbreitung verfolgen.",
      affiliation: "DASH Lab · SKKU",
      exploreSystems: "Systeme erkunden ↓",
      marquee: [
        "Deepfake-Erkennung",
        "Modellfreie Forensik",
        "Quellenblockierung",
        "Ausbreitungsvorhersage",
        "KI-Forensik-Assistent",
        "Synthetisches Watermarking",
        "Medienprovenienz",
        "Adversariale Robustheit",
      ],
      stats: [
        { v: "99.4%", l: "Erkennungs-AUROC", sub: "CVPR’24 Benchmark" },
        { v: "<120ms", l: "Analyselatenz", sub: "pro Frame @ 1080p" },
        { v: "14", l: "Peer-Review-Publikationen", sub: "seit 2023" },
        { v: "∞", l: "Analysierte synthetische Proben", sub: "fortlaufend" },
      ],
    },
    tools: {
      face: {
        eyeTitle: "EYE_L · 98.7%",
        eyeSub: "SYNTHETISCHER MARKER",
        noseTitle: "NOSE · SAUBER",
        noseSub: "FREQUENZANALYSE OK",
        browTitle: "BROW · 94.2%",
        browSub: "MIKROKANTEN-DRIFT",
        mouthTitle: "MOUTH · ANOMALIE",
        mouthSub: "DIFFUSIONSARTEFAKT",
        footer: "SML/FACE-V4 · 68 LANDMARKS · FRAME 00482",
      },
      sectionIdx: "02 / Systeme",
      eyebrow: "Produkte",
      titleLine: "Sicherere KI.",
      titleEm: "Sichere Welt.",
      subtitle:
        "Forensische Werkzeuge für Forschende, Redaktionen und Trust-Teams von Plattformen. Unsere Systeme analysieren Landmarken, Frequenzen und Mesh-Strukturen in Echtzeit — klicken Sie sich durch, um das Live-Terminal zu starten.",
      labels: {
        live: "Live",
        openLivePreview: "Live-Vorschau öffnen",
        openFullSystem: "Vollsystem öffnen",
      },
      cards: {
        detector: {
          title: "Deepfake-Detektor",
          kicker: "Forensische Analyse",
          desc:
            "Eine modellagnostische Pipeline zum Erkennen KI-generierter und manipulierter Bilder und Videos. Trainiert mit über 2 Mio. synthetischen Proben aus mehr als 40 Generatoren.",
          launch: "Deepfake-Erkennung starten",
          metrics: [
            { k: "AUROC", v: "99.4%" },
            { k: "Latenz", v: "118ms" },
            { k: "Modelle abgedeckt", v: "40+" },
          ],
        },
        assistant: {
          title: "Forensik-Assistent",
          kicker: "Forschungs-Copilot",
          desc:
            "Ein dialogbasierter Agent für Medienintegritäts-Analysten: hochladen, gegenprüfen, zitieren. Gestützt auf unseren Erkennungs-Stack und einen wachsenden Evidenzgraphen.",
          launch: "Forensik starten",
          metrics: [
            { k: "Evidenzquellen", v: "12.4k" },
            { k: "Antwortzeit", v: "1.2s" },
            { k: "Sprachen", v: "8" },
          ],
        },
      },
      useCases: {
        eyebrow: "Im Einsatz",
        items: [
          { h: "Redaktionen", b: "Nutzeraufnahmen vor der Veröffentlichung verifizieren." },
          { h: "Plattformen", b: "Synthetische Uploads skaliert und am Edge markieren." },
          { h: "Forschende", b: "Neue Erkennungsmethoden gegen unsere Systeme benchmarken." },
          { h: "Politik", b: "Evidenz für Ermittlungen und Regulierung prüfen." },
        ],
      },
    },
    research: {
      idx: "03 / Forschung",
      eyebrow: "Was wir untersuchen",
      titleMain: "Kern",
      titleEm: "Forschung.",
      subtitle:
        "Wir entwickeln die nächste Generation der KI-Sicherheit durch Grundlagenforschung und praktische forensische Implementierung. Drei parallele Linien: erkennen, verhindern, vorhersagen.",
      areas: [
        {
          tag: "DASH · CORE · STABLE",
          title: "Deepfake-Erkennung & KI-Forensik",
          desc:
            "Fortgeschrittene Forensik zum Identifizieren von Deepfakes und manipulierten Inhalten ohne umfangreiche Trainingsdaten oder Vorwissen über das generative Modell.",
          venues: ["CVPR ’25", "NeurIPS ’24"],
        },
        {
          tag: "SML · ALPHA · ACTIVE",
          title: "Blockierung an der Generierungsquelle",
          desc:
            "Architektonische Schutzmechanismen in KI-Modellen, die die Erstellung von Deepfakes auf grundlegender Ebene verhindern und synthetische Inhalte bereits an der Quelle sichtbar synthetisch machen.",
          venues: ["ICML ’25", "USENIX Sec."],
        },
        {
          tag: "NODAL · BETA · MONITORING",
          title: "Ausbreitungsvorhersage",
          desc:
            "Heuristische KI-Modelle, die die virale Verbreitung synthetischer Inhalte in digitalen Netzwerken verfolgen, analysieren und vorhersagen. Eingreifen, bevor die Kaskade entsteht.",
          venues: ["WWW ’25", "KDD ’24"],
        },
      ],
      publications: {
        eyebrow: "Ausgewählte Publikationen",
        title: "Aktuelle Arbeiten",
        all: "Alle Publikationen →",
        tags: {
          full: "Volltext",
          datasets: "Datensätze",
          workshop: "Workshop",
        },
      },
    },
    about: {
      idx: "04 / Über uns",
      eyebrow: "Über das Lab",
      headingPrefix: "Aus dem DASH Lab der",
      university: "Sungkyunkwan University",
      headingSuffix: "entstanden und zu einem Unternehmen für forensische Infrastruktur gewachsen.",
      body:
        "Wir sind zuerst Forschende. Wir schreiben Papers, bauen Benchmarks und härten die besten Ideen zu Produktionssystemen, die Redaktionen, Plattformen und politische Akteure tatsächlich einsetzen. Unsere These: Generative KI bleibt — also braucht das Web eine Vertrauensebene, die im gleichen Tempo arbeitet.",
      facts: [
        ["Gegründet", "2024"],
        ["HQ", "Suwon, KR"],
        ["Affiliation", "SKKU · DASH Lab"],
        ["Team", "12 Forschende"],
        ["Gefördert durch", "NRF, MSIT, Angels"],
        ["Hiring", "Offen (ML, Infra)"],
      ],
    },
    customers: {
      idx: "05",
      eyebrow: "Collaborating organizations",
      title: "Collaborators",
      subtitle: "Organisationen, mit denen wir an vertrauenswürdigeren Online-Informationen arbeiten.",
    },
    contact: {
      idx: "06 / Kontakt",
      titleLine: "Let's make",
      titleEm: "online information honest",
      titleEnd: "again.",
      subtitle:
        "Forschende, Trust-Teams, Redaktionen, politische Akteure — wenn Sie an synthetischen Medien arbeiten, möchten wir von Ihnen hören.",
      writeToUs: "Schreiben Sie uns",
      readLabNotes: "Lab Notes lesen",
      copy: "KOPIEREN",
      copied: "KOPIERT ✓",
      contacts: [
        {
          k: "Allgemein",
          v: "woo@securemachineslab.com",
          copyKey: "g",
          note: "Partnerschaften, Presse, Plattformintegrationen",
        },
      ],
      hq: "HQ",
      location: "Suwon-si, Gyeonggi-do",
      address: "Sungkyunkwan University · DASH Lab · Südkorea",
      footer: {
        privacy: "Datenschutz",
        terms: "Bedingungen",
        security: "Sicherheit",
        github: "GitHub ↗",
        status: "Alle Systeme betriebsbereit",
      },
    },
    visitors: {
      idx: "07 / Besucher",
      eyebrow: "Live-Reichweite",
      title: "Woher Besucher kommen",
      subtitle:
        "Eine Live-Karte der jüngsten Besuche bei Secure Machines Lab aus aller Welt.",
    },
  },
} satisfies Record<Language, DashTranslations>

export function isLanguage(value: string): value is Language {
  return SUPPORTED_LANGUAGES.some((language) => language.code === value)
}
