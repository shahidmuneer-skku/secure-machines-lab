/**
 * Selected publications of the DASH Lab (Sungkyunkwan University), shown on the landing page.
 *
 * Titles, venues and links were checked against the official proceedings pages / DOIs on 2026-10-02.
 * Two titles were corrected (#1 EuroS&P, #4 Moiré) and two entries are workshop papers (CVPR
 * Workshops), so their tag now says so.
 */
export type Publication = {
  year: string
  title: string
  venue: string
  tag: "Full" | "Datasets" | "Workshop"
  /** Official proceedings page or DOI. */
  url: string
}

export const PUBLICATIONS: Publication[] = [
  { year: "2025", title: "SoK: Systematization and benchmarking of deepfake detectors in a unified framework", venue: "IEEE EuroS&P", tag: "Full",
    url: "https://doi.org/10.1109/EuroSP63326.2025.00055" },
  { year: "2024", title: "UGAD: Universal generative AI detector utilizing frequency fingerprints", venue: "ACM CIKM", tag: "Full",
    url: "https://doi.org/10.1145/3627673.3680085" },
  { year: "2024", title: "Gradient alignment for cross-domain face anti-spoofing", venue: "CVPR", tag: "Full",
    url: "https://openaccess.thecvf.com/content/CVPR2024/html/Le_Gradient_Alignment_for_Cross-Domain_Face_Anti-Spoofing_CVPR_2024_paper.html" },
  { year: "2024", title: "Beyond the screen: Evaluating deepfake detectors under moiré pattern effects", venue: "CVPR", tag: "Workshop",
    url: "https://openaccess.thecvf.com/content/CVPR2024W/WMF/html/Tariq_Beyond_the_Screen_Evaluating_Deepfake_Detectors_under_Moire_Pattern_Effects_CVPRW_2024_paper.html" },
  { year: "2023", title: "Quality-agnostic deepfake detection with intra-model collaborative learning", venue: "ICCV", tag: "Full",
    url: "https://openaccess.thecvf.com/content/ICCV2023/html/Le_Quality-Agnostic_Deepfake_Detection_with_Intra-model_Collaborative_Learning_ICCV_2023_paper.html" },
  { year: "2022", title: "ADD: Frequency attention and multi-view based knowledge distillation to detect low-quality compressed deepfake images", venue: "AAAI", tag: "Full",
    url: "https://doi.org/10.1609/aaai.v36i1.19886" },
  { year: "2021", title: "FakeAVCeleb: A novel audio-video multimodal deepfake dataset", venue: "NeurIPS", tag: "Datasets",
    url: "https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/d9d4f495e875a2e075a1a4a6e1b9770f-Abstract-round2.html" },
  { year: "2021", title: "One detector to rule them all: Towards a general deepfake attack detection framework", venue: "WWW", tag: "Full",
    url: "https://doi.org/10.1145/3442381.3449809" },
  { year: "2021", title: "FReTAL: Generalizing deepfake detection using knowledge distillation and representation learning", venue: "CVPR", tag: "Workshop",
    url: "https://openaccess.thecvf.com/content/CVPR2021W/WMF/html/Kim_FReTAL_Generalizing_Deepfake_Detection_Using_Knowledge_Distillation_and_Representation_Learning_CVPRW_2021_paper.html" },
  { year: "2020", title: "OC-FakeDect: Classifying deepfakes using one-class variational autoencoder", venue: "CVPR", tag: "Workshop",
    url: "https://openaccess.thecvf.com/content_CVPRW_2020/html/w39/Khalid_OC-FakeDect_Classifying_Deepfakes_Using_One-Class_Variational_Autoencoder_CVPRW_2020_paper.html" },
]

/**
 * Benchmark figures the previous landing page showed. They are kept here but NOT displayed until the
 * lab links a source for each (scope + publication/table). On 2026-10-02 none could be matched to a
 * publication: e.g. no CVPR 2024 paper of the lab reports 99.4 % AUROC.
 */
export type Benchmark = { messageIndex: number; sourceUrl: string | null }
export const BENCHMARKS: Benchmark[] = [
  { messageIndex: 0, sourceUrl: null }, // "99.4% · Detection AUROC · CVPR’24 benchmark"
  { messageIndex: 1, sourceUrl: null }, // "<120 ms · Per-frame analysis · 1080p video"
  { messageIndex: 2, sourceUrl: null }, // "14 · Peer-reviewed papers · since 2023"
  { messageIndex: 3, sourceUrl: null }, // "40+ · Generators covered"
]
