"use client"

import { useState } from "react"
import Link from "next/link"
import type { DashTranslations } from "@/lib/marketing/i18n"

export default function ContactSection({
  t,
}: {
  t: DashTranslations["contact"]
}) {
  const [copied, setCopied] = useState<string | null>(null)

  function copy(text: string, key: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key)
      setTimeout(() => setCopied(null), 1600)
    })
  }

  const contacts = t.contacts
  const titleEmBreak = t.titleEm.lastIndexOf(" ")
  const titleEmFirstLine = t.titleEm.slice(0, titleEmBreak)
  const titleEmSecondLine = t.titleEm.slice(titleEmBreak + 1)

  return (
    <section id="contact" style={{
      position: "relative", padding: "clamp(100px, 14vh, 160px) clamp(20px, 4vw, 48px) 40px", zIndex: 2,
    }}>
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>
        <div className="contact-grid" style={{
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 80, alignItems: "start",
        }}>
          <div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.3em", textTransform: "uppercase", color: "var(--ink-faint)", marginBottom: 20 }}>
              {t.idx}
            </div>
            <h2 style={{
              margin: 0, fontSize: "48px!important", fontWeight: 500,
              lineHeight: 0.9, letterSpacing: "-0.03em",
            }}>
              {t.titleLine}<br />
              <em style={{ fontFamily: "var(--serif)", fontStyle: "italic", color: "var(--accent)", fontWeight: 400 }}>
                {titleEmFirstLine}<br />{titleEmSecondLine}
              </em><br />
              {t.titleEnd}
            </h2>
            <p style={{ marginTop: 32, fontSize: 18, lineHeight: 1.55, color: "var(--ink-dim)", maxWidth: 460 }}>
              {t.subtitle}
            </p>

            <div style={{ marginTop: 40, display: "flex", gap: 14, flexWrap: "wrap" }}>
              <a href="mailto:woo@securemachineslab.com" className="contact-cta">
                <span>{t.writeToUs}</span>
                <span className="contact-cta-arrow">→</span>
              </a>
              <a href="#" className="contact-cta contact-cta--ghost">
                <span>{t.readLabNotes}</span>
              </a>
            </div>
          </div>

          <div className="contact-list">
            {contacts.map((c, i) => (
              <div key={i} className="contact-row" onClick={() => copy(c.v, c.copyKey)}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.26em", textTransform: "uppercase", color: "var(--ink-faint)" }}>
                    {c.k}
                  </div>
                  <span className="contact-copy">{copied === c.copyKey ? t.copied : t.copy}</span>
                </div>
                <div className="contact-val">{c.v}</div>
                <div style={{ fontSize: 13, color: "var(--ink-dim)", marginTop: 6 }}>{c.note}</div>
              </div>
            ))}
            <div className="contact-loc">
              <div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.26em", textTransform: "uppercase", color: "var(--ink-faint)", marginBottom: 10 }}>{t.hq}</div>
                <div style={{ fontSize: 20, fontWeight: 500 }}>{t.location}</div>
                <div style={{ color: "var(--ink-dim)", fontSize: 14, marginTop: 4 }}>{t.address}</div>
              </div>
              <div className="contact-map">
                <span className="contact-pin"></span>
              </div>
            </div>
          </div>
        </div>

        {/* Giant footer mark */}
        {/* <div className="footer-mark">
          <div className="footer-mark-row">
            <span>SECURE</span>
            <span className="fm-italic">MACHINES</span>
          </div>
          <div className="footer-mark-row fm-outline">
            <span>LAB</span>
            <span className="fm-year">— SML · {new Date().getFullYear()}</span>
          </div>
        </div> */}

        <div className="footer-bar">
          <div>&copy; {new Date().getFullYear()} Secure Machines Lab Inc.</div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <Link href="/privacy">{t.footer.privacy}</Link>
            <Link href="/terms">{t.footer.terms}</Link>
            <a href="#">{t.footer.security}</a>
            <a href="#">{t.footer.github}</a>
          </div>
          <div className="footer-status">
            <span className="led" style={{ background: "var(--ok)", boxShadow: "0 0 8px var(--ok)" }}></span>
            {t.footer.status}
          </div>
        </div>
      </div>
    </section>
  )
}
