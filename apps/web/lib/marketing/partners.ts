import type { Language } from "./i18n"
import { watermarkGalleryImages } from "./watermark-gallery.generated"

/**
 * Partner logos for the landing page, from the generated watermark-gallery manifest.
 *
 * Most non-ASCII file names (Hangul, "Göttingen") were committed from macOS in Unicode NFD, and git
 * keeps them that way on every checkout; the manifest lists the same NFD paths. URLs are therefore used
 * exactly as the manifest gives them (normalising them to NFC made those logos 404), and only the
 * lookup of official names below normalises to NFC.
 *
 * Names are the organisations' official English names, as printed on their logos.
 * "Polizei NRW" and "LKA NRW" look alike but are different bodies (state police and the State
 * Criminal Police Office), so both stay.
 */
const OFFICIAL_NAMES: Record<string, string> = {
  "Emblem_of_the_Prosecution_Service_of_Korea.svg.png": "Prosecution Service of Korea",
  "Logo_LKA_NRW.jpg": "Landeskriminalamt Nordrhein-Westfalen (LKA NRW)",
  "Logo_Uni_Göttingen_2022.png": "Georg-August-Universität Göttingen",
  "NRW.png": "Polizei Nordrhein-Westfalen",
  "wuppertal.png": "Bergische Universität Wuppertal",
  "경찰청.png": "Korean National Police Agency",
  "KIPOT영어.png": "Korea Institute of Police Technology",
  "KIPOT한국어.png": "Korea Institute of Police Technology",
  "과기정통부영어.png": "Ministry of Science and ICT",
  "과기정통부한글.png": "Ministry of Science and ICT",
  "방통위영어.png": "Korea Media and Communications Commission",
  "방통위한글.png": "Korea Media and Communications Commission",
  "선관위영어.png": "National Election Commission of the Republic of Korea",
  "선관위.png": "National Election Commission of the Republic of Korea",
  "성대영어.jpg": "Sungkyunkwan University",
  "성대한국어.jpg": "Sungkyunkwan University",
  "안전연구소영어.png": "AI Safety Institute",
  "안전연구소한글.png": "AI Safety Institute",
}

export type Partner = { src: string; name: string }

export function partnersFor(language: Language): Partner[] {
  const list = [...watermarkGalleryImages.common, ...(language === "ko" ? watermarkGalleryImages.korean : watermarkGalleryImages.english)]
  return list.map((logo) => {
    const file = decodeURI(logo.src).normalize("NFC").split("/").pop() ?? ""
    return { src: logo.src, name: OFFICIAL_NAMES[file] ?? logo.alt.normalize("NFC") }
  })
}
