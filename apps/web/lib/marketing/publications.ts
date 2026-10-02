/** Selected publications of the DASH Lab (Sungkyunkwan University), shown on the landing page. */
export type Publication = { year: string; title: string; venue: string; tag: "Full" | "Datasets" | "Workshop" }

export const PUBLICATIONS: Publication[] = [
  { year: "2025", title: "SOK: Systematization of deepfake detection and generation", venue: "EuroS&P", tag: "Full" },
  { year: "2024", title: "UGAD: Universal generative AI detector utilizing frequency fingerprints", venue: "ACM CIKM", tag: "Full" },
  { year: "2024", title: "Gradient alignment for cross-domain face anti-spoofing", venue: "CVPR", tag: "Full" },
  { year: "2024", title: "Beyond the screen: Moiré pattern effects on deepfake detectors", venue: "CVPR", tag: "Full" },
  { year: "2023", title: "Quality-agnostic deepfake detection with intra-model collaborative learning", venue: "ICCV", tag: "Full" },
  { year: "2022", title: "ADD: Frequency attention and multi-view based knowledge distillation to detect low-quality compressed deepfake images", venue: "AAAI", tag: "Full" },
  { year: "2021", title: "FakeAVCeleb: A novel audio-video multimodal deepfake dataset", venue: "NeurIPS", tag: "Datasets" },
  { year: "2021", title: "One detector to rule them all: Towards a general deepfake attack detection framework", venue: "WWW", tag: "Full" },
  { year: "2021", title: "FReTAL: Generalizing deepfake detection using knowledge distillation and representation learning", venue: "CVPR", tag: "Full" },
  { year: "2020", title: "OC-FakeDect: Classifying deepfakes using one-class variational autoencoder", venue: "CVPR", tag: "Workshop" },
]
