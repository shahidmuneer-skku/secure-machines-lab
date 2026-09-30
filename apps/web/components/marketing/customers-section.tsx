import Image from "next/image"
import type { DashTranslations, Language } from "@/lib/marketing/i18n"
import { watermarkGalleryImages } from "@/lib/marketing/watermark-gallery.generated"

function CustomersMap() {
  return (
    <svg className="customers-map" viewBox="0 0 1600 640" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <g className="customers-map__land">
        <path d="M92 154c42-61 113-93 181-87l39 33 55 3 22 43-25 32-48 3-22 31-48-3-29 40-55 18-41-35-40-62 6-43z" />
        <path d="M360 288l52 18 35 55-10 61 30 64-26 95-37 34-29-49 3-70-28-55 6-62 24-45z" />
        <path d="M548 74l43-33 40 17-5 55-45 8-32-22z" />
        <path d="M700 170l52-30 74 18 35 42-23 37-51 4-27 36-52-6-31-52 23-49z" />
        <path d="M790 291l63-14 55 37 8 75-41 112-70-13-36-89 21-108z" />
        <path d="M879 145l88-35 77 19 78-36 107 29 80 3 87 57-25 41-78 2-69 38-72-9-67 31-70-15-47 26-64-20-42-43 7-48z" />
        <path d="M1193 453l65-27 82 25 21 57-57 43-86-23-31-48 6-27z" />
        <path d="M1431 365l23-18 30 11 2 33-33 16-29-17 7-25z" />
      </g>
      <g className="customers-map__network">
        <path d="M255 182 438 381 741 212 1050 179 1288 483" />
        <path d="M438 381 837 364 1050 179" />
        <path d="M741 212 837 364 1288 483" />
        <circle cx="255" cy="182" r="7" />
        <circle cx="438" cy="381" r="7" />
        <circle cx="741" cy="212" r="7" />
        <circle cx="837" cy="364" r="7" />
        <circle cx="1050" cy="179" r="7" />
        <circle cx="1288" cy="483" r="7" />
      </g>
    </svg>
  )
}

export default function CustomersSection({
  t,
  language,
}: {
  t: DashTranslations["customers"]
  language: Language
}) {
  const localeImages = language === "ko"
    ? watermarkGalleryImages.korean
    : watermarkGalleryImages.english
  const images = [...watermarkGalleryImages.common, ...localeImages]

  if (images.length === 0) return null

  return (
    <section className="customers-section" aria-labelledby="customers-title">
      <CustomersMap />
      <div className="customers-section__inner">
        <header id="customers" className="customers-header">
          <div className="customers-header__meta">
            {t.idx && <>
              <span>{t.idx}</span>
              <span className="customers-header__rule" aria-hidden="true"></span>
            </>}
            <span>{t.eyebrow}</span>
          </div>
          <div className="customers-header__copy">
            <h2 id="customers-title">{t.title}</h2>
            <p>{t.subtitle}</p>
          </div>
        </header>

        <div className="customers-logo-grid">
          {images.map((image) => (
            <div
              className={`customers-logo-card${image.prominent ? " customers-logo-card--prominent" : ""}${image.authority ? " customers-logo-card--authority" : ""}${image.police ? " customers-logo-card--police" : ""}${image.broadcasting ? " customers-logo-card--broadcasting" : ""}${image.compact ? " customers-logo-card--compact" : ""}`}
              key={image.src}
            >
              <Image src={image.src} alt={image.alt} width={640} height={276} sizes="(max-width: 768px) 45vw, 320px" />
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
