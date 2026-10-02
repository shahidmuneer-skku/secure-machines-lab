"use client"

import { IconArrowDown, IconInfoCircle, IconPlayerPause, IconPlayerPlay, IconX } from "@tabler/icons-react"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import dynamic from "next/dynamic"
import Image from "next/image"
import { useTranslations } from "next-intl"
import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react"

import { createScanController, REGIONS, type RegionId, type ScanController } from "./controller"
import type { SceneStatus } from "./face-canvas"
import styles from "./scan-hero.module.css"
import { sampleScan, STAGE_REST, STAGES, type LayerMode } from "./timeline"
import { useScanEnvironment } from "./use-scan-environment"

// three.js and the scene load after hydration; the headline, CTAs and poster never wait for them.
const FaceCanvas = dynamic(() => import("./face-canvas"), { ssr: false })

const CONTROL_SELECTOR = "a, button, input, select, textarea, label, [role='button'], [data-control]"
const LAYERS: LayerMode[] = ["follow", "surface", "mesh", "evidence"]
const LICENSE_URL = "https://creativecommons.org/licenses/by/3.0/"

/**
 * Hero: a 3D head undergoing a scroll-controlled forensic scan (intro → scan → inspect → explain →
 * hand-off to the real upload). Semantic HTML carries every word and control; the canvas is decoration
 * driven by one master ScrollTrigger timeline through a shared controller (no per-frame React state).
 * Everything shown is an illustrative demonstration, never a detection result.
 */
export function ScanHero() {
  const t = useTranslations("landing.scan")
  const env = useScanEnvironment()
  const { mode } = env
  const ctlRef = useRef<ScanController>(createScanController())
  const rootRef = useRef<HTMLElement>(null)
  const stageElRef = useRef<HTMLDivElement>(null)
  const boxRef = useRef<HTMLDivElement>(null)
  const textRef = useRef<HTMLDivElement>(null)
  const panelRefs = useRef<(HTMLDivElement | null)[]>([])
  const reportRef = useRef<HTMLElement | null>(null)
  const chipRefs = useRef<Partial<Record<RegionId, HTMLButtonElement | null>>>({})
  const triggerRef = useRef<HTMLElement | null>(null)
  const stageIndexRef = useRef(0)
  const pickRaf = useRef(0)

  const [status, setStatus] = useState<SceneStatus>("loading")
  const [stage, setStage] = useState(0)
  const [selected, setSelected] = useState<RegionId | null>(null)
  const [layer, setLayer] = useState<LayerMode>("follow")
  const [paused, setPaused] = useState(false)

  const sceneOn = env.hydrated && env.webgl && status !== "error"

  // ---- keep the controller in sync with the environment and UI state ----
  useEffect(() => {
    const ctl = ctlRef.current
    ctl.mode = mode
    ctl.reducedMotion = env.reducedMotion
    ctl.pointerFollow = env.finePointer && mode === "scroll"
    ctl.motionPaused = paused
    ctl.invalidate()
  }, [mode, env.reducedMotion, env.finePointer, paused])

  // ---- HTML side of the timeline: panels, report, stage index (written directly, no re-render) ----
  const applyHtml = useCallback((p: number) => {
    const ctl = ctlRef.current
    const s = sampleScan(p)
    if (ctl.mode === "scroll") {
      panelRefs.current.forEach((el, i) => {
        if (!el) return
        const o = s.panels[i]
        el.style.opacity = o.toFixed(3)
        el.style.transform = o > 0.999 ? "" : `translate3d(0, ${((1 - o) * 14).toFixed(1)}px, 0)`
        el.style.pointerEvents = o > 0.5 ? "auto" : "none"
      })
      const r = reportRef.current
      if (r) {
        r.style.opacity = s.report.toFixed(3)
        r.style.transform = `translateY(calc(-50% + ${((1 - s.report) * 16).toFixed(1)}px))`
      }
    }
    if (s.stage !== stageIndexRef.current) {
      stageIndexRef.current = s.stage
      setStage(s.stage)
      // A pinned layer view stays until "Follow scroll" or until the inspect stage is left.
      if (s.stage !== 2 && ctl.layer !== "follow") {
        ctl.layer = "follow"
        setLayer("follow")
      }
    }
  }, [])

  // ---- the master scroll timeline (scroll mode only) ----
  useEffect(() => {
    const root = rootRef.current
    const ctl = ctlRef.current
    if (!root) return
    if (mode !== "scroll") {
      // Manual mode: panels are shown by React; drop any inline styles from the scroll mode.
      panelRefs.current.forEach((el) => el?.removeAttribute("style"))
      reportRef.current?.removeAttribute("style")
      ctl.progress = STAGE_REST[stageIndexRef.current]
      ctl.shownProgress = ctl.progress
      ctl.invalidate()
      return
    }
    gsap.registerPlugin(ScrollTrigger)
    const panels = panelRefs.current
    const proxy = { p: 0 }
    const tl = gsap.timeline({
      defaults: { ease: "none" },
      scrollTrigger: { trigger: root, start: "top top", end: "bottom bottom", scrub: 0.6, invalidateOnRefresh: true },
    })
    tl.to(proxy, {
      p: 1,
      duration: 1,
      onUpdate: () => {
        ctl.progress = proxy.p
        applyHtml(proxy.p)
        ctl.invalidate()
      },
    })
    const st = tl.scrollTrigger!
    // Reloading or jumping half-way down: show that state at once instead of replaying the story.
    const snap = () => {
      st.getTween()?.progress(1)
      tl.progress(st.progress)
      proxy.p = st.progress
      ctl.progress = st.progress
      applyHtml(st.progress)
      ctl.invalidate()
    }
    snap()
    ScrollTrigger.addEventListener("refresh", snap)
    return () => {
      ScrollTrigger.removeEventListener("refresh", snap)
      st.kill()
      tl.kill()
      panels.forEach((el) => el?.removeAttribute("style"))
      reportRef.current?.removeAttribute("style")
    }
  }, [mode, applyHtml])

  // ---- measurements: navigation height, text column edge ----
  useEffect(() => {
    const ctl = ctlRef.current
    const root = rootRef.current
    const measure = () => {
      const host = mode === "scroll" ? stageElRef.current : boxRef.current
      const nav = document.querySelector("header")
      ctl.navHeight = nav ? Math.round(nav.getBoundingClientRect().height) : 72
      root?.style.setProperty("--nav-h", `${ctl.navHeight}px`)
      if (host && textRef.current) {
        ctl.textRight = mode === "scroll" ? textRef.current.getBoundingClientRect().right - host.getBoundingClientRect().left : 0
      }
      ctl.invalidate()
    }
    measure()
    const ro = new ResizeObserver(measure)
    if (root) ro.observe(root)
    if (textRef.current) ro.observe(textRef.current)
    return () => ro.disconnect()
  }, [mode])

  // ---- render only while on screen and the tab is visible ----
  useEffect(() => {
    const ctl = ctlRef.current
    const root = rootRef.current
    if (!root) return
    let inView = true
    const update = () => {
      ctl.visible = inView && !document.hidden
      if (ctl.visible) ctl.invalidate()
    }
    const io = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting
      update()
    }, { rootMargin: "120px 0px" })
    io.observe(root)
    document.addEventListener("visibilitychange", update)
    return () => {
      io.disconnect()
      document.removeEventListener("visibilitychange", update)
    }
  }, [])

  // ---- development hook for visual checks (window.__scan) ----
  useEffect(() => {
    if (process.env.NODE_ENV === "production") return
    const w = window as unknown as { __scan?: ScanController }
    w.__scan = ctlRef.current
    return () => {
      delete w.__scan
    }
  }, [])

  // ---- regions ----
  const closeRegion = useCallback((restoreFocus: boolean) => {
    const ctl = ctlRef.current
    const id = ctl.selected
    ctl.selected = null
    setSelected(null)
    ctl.invalidate()
    if (restoreFocus) (triggerRef.current ?? (id ? chipRefs.current[id] : null))?.focus()
    triggerRef.current = null
  }, [])

  const openRegion = useCallback((id: RegionId, trigger: HTMLElement | null) => {
    const ctl = ctlRef.current
    if (ctl.selected === id) {
      closeRegion(!!trigger)
      return
    }
    ctl.selected = id
    triggerRef.current = trigger
    setSelected(id)
    ctl.invalidate()
  }, [closeRegion])

  useEffect(() => {
    if (!selected) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault()
        closeRegion(true)
      }
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [selected, closeRegion])

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const ctl = ctlRef.current
    const host = e.currentTarget
    const rect = host.getBoundingClientRect()
    ctl.pointer.x = e.clientX - rect.left
    ctl.pointer.y = e.clientY - rect.top
    ctl.pointer.inside = true
    ctl.pointer.overControl = !!(e.target as Element).closest(CONTROL_SELECTOR)
    if (e.pointerType === "mouse" && !pickRaf.current) {
      pickRaf.current = requestAnimationFrame(() => {
        pickRaf.current = 0
        const over = ctl.pointer.inside && !ctl.pointer.overControl ? ctl.pick(ctl.pointer.x, ctl.pointer.y) : null
        if (over !== ctl.hover) {
          ctl.hover = over
          host.style.cursor = over ? "pointer" : ""
        }
        ctl.invalidate()
      })
    } else {
      ctl.invalidate()
    }
  }

  const onPointerLeave = (e: ReactPointerEvent<HTMLDivElement>) => {
    const ctl = ctlRef.current
    ctl.pointer.inside = false
    ctl.hover = null
    e.currentTarget.style.cursor = ""
    ctl.invalidate()
  }

  const onSceneClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if ((e.target as Element).closest(CONTROL_SELECTOR) || (e.target as Element).closest("[data-card]")) return
    const ctl = ctlRef.current
    const rect = e.currentTarget.getBoundingClientRect()
    const id = ctl.pick(e.clientX - rect.left, e.clientY - rect.top)
    if (id) openRegion(id, null)
    else if (ctl.selected) closeRegion(false)
  }

  // ---- stages ----
  const goToStage = useCallback((i: number, behavior?: ScrollBehavior) => {
    const ctl = ctlRef.current
    const root = rootRef.current
    if (!root) return
    if (ctl.mode === "scroll") {
      const top = root.getBoundingClientRect().top + window.scrollY
      const length = root.offsetHeight - window.innerHeight
      const smooth = !ctl.reducedMotion && !ctl.motionPaused
      window.scrollTo({ top: top + STAGE_REST[i] * length, behavior: behavior ?? (smooth ? "smooth" : "auto") })
    } else {
      stageIndexRef.current = i
      setStage(i)
      ctl.progress = STAGE_REST[i]
      if (i !== 2 && ctl.layer !== "follow") {
        ctl.layer = "follow"
        setLayer("follow")
      }
      ctl.invalidate()
    }
  }, [])

  const registerPanel = useCallback((i: number, el: HTMLDivElement | null) => {
    panelRefs.current[i] = el
  }, [])

  /** Keyboard focus landing in a faded-out panel (scroll mode sets its opacity) scrolls the story to it. */
  const revealOnFocus = useCallback((i: number, el: HTMLElement) => {
    if (Number(el.style.opacity || "1") < 0.5) goToStage(i, "auto")
  }, [goToStage])

  const chooseLayer = (m: LayerMode) => {
    ctlRef.current.layer = m
    setLayer(m)
    ctlRef.current.invalidate()
  }

  const onStatus = useCallback((s: SceneStatus) => setStatus(s), [])

  // ---- pieces ----
  const regionChips = (
    <div className={styles.chips} role="group" aria-labelledby="scan-regions-label">
      <span id="scan-regions-label" className={styles.groupLabel}>{t("regions.group")}</span>
      {REGIONS.map((id) => (
        <button key={id} type="button" className={styles.chip} data-region={id}
          ref={(el) => { chipRefs.current[id] = el }}
          aria-expanded={selected === id} aria-controls="scan-region-card"
          onClick={(e) => openRegion(id, e.currentTarget)}>
          {t(`regions.${id}.label`)}
        </button>
      ))}
    </div>
  )

  const layerControls = (
    <div className={styles.layers} role="group" aria-labelledby="scan-layers-label">
      <span id="scan-layers-label" className={styles.groupLabel}>{t("layers.group")}</span>
      {LAYERS.map((m) => (
        <button key={m} type="button" className={styles.chip} aria-pressed={layer === m} onClick={() => chooseLayer(m)}>
          {t(`layers.${m}`)}
        </button>
      ))}
    </div>
  )

  const pauseButton = (
    <button type="button" className={styles.iconBtn} aria-pressed={paused} onClick={() => setPaused((v) => !v)}>
      {paused ? <IconPlayerPlay size={16} aria-hidden /> : <IconPlayerPause size={16} aria-hidden />}
      {paused ? t("resume") : t("pause")}
    </button>
  )

  const explanation = selected && (
    <div id="scan-region-card" className={styles.explain} data-card
      ref={(el) => { ctlRef.current.dom.card = el }}
      role="group" aria-labelledby="scan-region-title">
      <span className={styles.leader} data-leader aria-hidden />
      <div className={`${styles.card} ${styles.explainBox}`} data-box>
        <div className={styles.explainHead}>
          <h3 id="scan-region-title">{t(`regions.${selected}.label`)}</h3>
          <button type="button" className={styles.close} aria-label={t("regions.close")} onClick={() => closeRegion(true)}>
            <IconX size={18} aria-hidden />
          </button>
        </div>
        <p>{t(`regions.${selected}.body`)}</p>
        <p className={styles.caveat}>{t("regions.caveat")}</p>
      </div>
    </div>
  )
  const report = (
    <aside className={styles.report} ref={(el) => { reportRef.current = el }} aria-labelledby="scan-report-title">
      <div className={styles.card}>
        <div className={styles.reportHead}>
          <h3 id="scan-report-title">{t("report.title")}</h3>
          <span className={styles.tag}>{t("report.tag")}</span>
        </div>
        <dl className={styles.reportBody}>
          <div className={styles.reportRow}>
            <dt>{t("report.subject")}</dt>
            <dd>{t("report.subjectValue")}</dd>
          </div>
          <div className={styles.reportRow}>
            <dt>{t("report.region")}</dt>
            <dd><span className={styles.swatch} aria-hidden />{t("report.regionValue")}</dd>
            <dd>{t("report.regionNote")}</dd>
          </div>
          <div className={styles.reportRow}>
            <dt>{t("report.provenance")}</dt>
            <dd><span className={styles.swatch} data-tone="neutral" aria-hidden />{t("report.provenanceValue")}</dd>
            <dd>{t("report.provenanceNote")}</dd>
          </div>
          <div className={styles.reportRow}>
            <dt>{t("report.findings")}</dt>
            <dd>
              <ul className={styles.findings}>
                {(t.raw("report.findingsList") as string[]).map((f) => <li key={f}>{f}</li>)}
              </ul>
            </dd>
          </div>
        </dl>
      </div>
    </aside>
  )

  const sceneLayers = (
    <>
      <Image src="/images/hero/face-poster.webp" alt={t("poster")} width={900} height={1100} priority
        sizes="(max-width: 767px) 90vw, 50vw" className={styles.poster} data-hidden={status === "ready" ? "true" : "false"} />
      {sceneOn && (
        <div className={styles.canvasLayer} data-ready={status === "ready"} aria-hidden>
          <FaceCanvas key={`${mode}-${env.tier}`} controllerRef={ctlRef} tier={env.tier} onStatus={onStatus} />
        </div>
      )}
      <div className={styles.overlay} aria-hidden>
        <div className={styles.frame} ref={(el) => { ctlRef.current.dom.frame = el }}>
          <span className={styles.frameCaption}>{t("frame")}</span>
        </div>
        {REGIONS.map((id) => (
          <div key={id} className={styles.label} ref={(el) => { ctlRef.current.dom.labels[id] = el }}>
            <span className={styles.leader} data-leader />
            <span className={styles.labelBox} data-box>
              {t(`regions.${id}.short`)}
              <small>{t("regions.illustrative")}</small>
            </span>
          </div>
        ))}
      </div>
    </>
  )

  const stagePanels = [1, 2, 3, 4].map((i) => (
    <StagePanel key={STAGES[i]} index={i} active={stage === i} register={registerPanel} onFocusReveal={revealOnFocus}
      extra={STAGES[i] === "inspect" && mode === "scroll" ? layerControls : null} />
  ))

  const steps = (
    <nav aria-label={t("steps")} id="scan-steps">
      <ol className={styles.steps}>
        {STAGES.map((key, i) => (
          <li key={key}>
            <button type="button" className={styles.step} aria-current={stage === i ? "step" : undefined}
              data-done={i < stage ? "true" : "false"} onClick={() => goToStage(i)}>
              <span className={styles.stepNum} aria-hidden>{String(i + 1).padStart(2, "0")}</span>
              {t(`stages.${key}.label`)}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )

  const credit = (
    <p className={styles.credit}>
      <a href={LICENSE_URL} target="_blank" rel="noopener noreferrer license">{t("credit")}</a>
      {!sceneOn && env.hydrated && <> · {t("fallback")}</>}
    </p>
  )

  const scroll = mode === "scroll"
  const hostProps = { onPointerMove, onPointerLeave, onClick: onSceneClick }

  return (
    <section ref={rootRef} id="scan" className={styles.root} data-mode={mode} aria-labelledby="scan-title">
      <div ref={stageElRef} className={styles.stage} data-scene={sceneOn ? "on" : "off"} {...(scroll ? hostProps : {})}>
        <div className={styles.atmosphere} data-static={status !== "ready" ? "true" : "false"} aria-hidden />
        {scroll && sceneLayers}
        {scroll && explanation}

        <div className={styles.content}>
          <div ref={textRef} className={styles.textCol}>
            {/* Intro panel: the page's h1 and the two calls to action, visible immediately. */}
            <div className={styles.panel} data-panel="0" ref={(el) => { panelRefs.current[0] = el }}
              onFocusCapture={(e) => revealOnFocus(0, e.currentTarget)}>
              <p className={styles.eyebrow}>{t("eyebrow")}</p>
              <h1 id="scan-title" className={styles.title}>{t("title")}</h1>
              <p className={styles.subtitle}>{t("subtitle")}</p>
              <p className={styles.description}>{t("description")}</p>
              <div className={styles.ctas}>
                <a href="#trial" className={styles.btnPrimary}>{t("primary")}<IconArrowDown size={18} aria-hidden /></a>
                <button type="button" className={styles.btnSecondary} onClick={() => {
                  goToStage(1)
                  if (!scroll) boxRef.current?.scrollIntoView({ block: "center", behavior: env.reducedMotion ? "auto" : "smooth" })
                }}>{t("secondary")}</button>
              </div>
              <p className={styles.hint}>{scroll ? t("hint") : t("hintManual")}</p>
            </div>
            {scroll && stagePanels}
          </div>

          {!scroll && (
            <div ref={boxRef} className={styles.sceneBox} data-scene={sceneOn ? "on" : "off"} {...hostProps}>
              {sceneLayers}
            </div>
          )}

          {scroll ? (
            <div className={styles.sceneCol}>
              <div className={styles.sceneTop}>
                <p className={styles.sceneLabel}><strong>{t("sceneLabel")}</strong>{t("sceneNote")}</p>
                {pauseButton}
              </div>
              {regionChips}
              <div className={styles.sceneBottom}>{credit}</div>
            </div>
          ) : (
            <div className={styles.copy}>
              <p className={styles.sceneLabel}><strong>{t("sceneLabel")}</strong>{t("sceneNote")}</p>
              <div className={styles.panel} data-panel="manual-intro" data-active={stage === 0}>
                <p className={styles.stageBody}>{t("stages.intro.body")}</p>
              </div>
              {stagePanels}
              {stage === 3 && report}
              <div className={styles.copyChrome}>
                {stage === 2 && layerControls}
                {regionChips}
                {explanation}
                <div>{pauseButton}</div>
                {credit}
              </div>
            </div>
          )}

          <div className={styles.bar}>
            {steps}
            <a href="#trial" className={styles.skip}>{t("skip")}<IconArrowDown size={16} aria-hidden /></a>
          </div>
        </div>

        {scroll && report}
      </div>
    </section>
  )
}

/** One stage's copy (scan, inspect, explain, hand-off). Visibility is driven by the timeline or the stage buttons. */
function StagePanel({ index, active, register, onFocusReveal, extra }: {
  index: number
  active: boolean
  register: (index: number, el: HTMLDivElement | null) => void
  onFocusReveal: (index: number, el: HTMLElement) => void
  extra: ReactNode
}) {
  const t = useTranslations("landing.scan")
  const key = STAGES[index]
  return (
    <div className={styles.panel} data-panel={index} data-active={active}
      ref={(el) => register(index, el)} onFocusCapture={(e) => onFocusReveal(index, e.currentTarget)}>
      <p className={styles.stageIndex}>{t("stageCount", { n: index + 1 })} · {t(`stages.${key}.label`)}</p>
      <h2 className={styles.stageTitle}>{t(`stages.${key}.title`)}</h2>
      <p className={styles.stageBody}>{t(`stages.${key}.body`)}</p>
      {key === "scan" && (
        <p className={styles.note}><IconInfoCircle size={16} aria-hidden />{t("stages.scan.note")}</p>
      )}
      {extra}
      {key === "handoff" && (
        <div className={styles.ctas}>
          <a href="#trial" className={styles.btnPrimary}>{t("stages.handoff.cta")}<IconArrowDown size={18} aria-hidden /></a>
        </div>
      )}
    </div>
  )
}
