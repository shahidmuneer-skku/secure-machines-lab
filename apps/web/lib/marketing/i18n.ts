export const SUPPORTED_LANGUAGES = [
  { code: "en", label: "EN", nativeName: "English", htmlLang: "en" },
  { code: "ko", label: "KO", nativeName: "한국어", htmlLang: "ko" },
  { code: "de", label: "DE", nativeName: "Deutsch", htmlLang: "de" },
] as const

export type Language = (typeof SUPPORTED_LANGUAGES)[number]["code"]

const en = {
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
}

export type DashTranslations = typeof en

export const dashTranslations = {
  en,
  ko: {
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
  },
  de: {
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
  },
} satisfies Record<Language, DashTranslations>

export function isLanguage(value: string): value is Language {
  return SUPPORTED_LANGUAGES.some((language) => language.code === value)
}
