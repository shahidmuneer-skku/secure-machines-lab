"use client"

import { useEffect, useRef } from "react"

interface Point {
  x: number
  y: number
  vx: number
  vy: number
  originX: number
  originY: number
}

export default function SpiderCursor() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    if (!window.matchMedia("(pointer: fine)").matches) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const mouse = { x: -9999, y: -9999 }
    const POINT_COUNT = 140
    const CONNECT_DIST = 150
    const MOUSE_RADIUS = 250
    const REPEL_STRENGTH = 0.05
    const RETURN_STRENGTH = 0.018
    let points: Point[] = []
    let w = 0, h = 0
    let heroEl: HTMLElement | null = null
    let heroRect = { top: 0, bottom: 0, left: 0, right: 0 }
    let raf: number
    let isInHero = false

    function resize() {
      w = window.innerWidth
      h = window.innerHeight
      canvas!.width = w
      canvas!.height = h
      canvas!.style.width = w + "px"
      canvas!.style.height = h + "px"

      heroEl = document.getElementById("hero")
      if (heroEl) {
        const r = heroEl.getBoundingClientRect()
        heroRect = { top: r.top + window.scrollY, bottom: r.bottom + window.scrollY, left: r.left, right: r.right }
      }

      // Distribute points across the hero area
      points = []
      const heroH = heroEl ? heroEl.offsetHeight : h
      for (let i = 0; i < POINT_COUNT; i++) {
        const x = Math.random() * w
        const y = Math.random() * heroH
        points.push({ x, y, vx: 0, vy: 0, originX: x, originY: y })
      }
    }

    function onPointerMove(e: PointerEvent) {
      mouse.x = e.clientX
      mouse.y = e.clientY + window.scrollY
    }
    function onScroll() {
      if (heroEl) {
        const r = heroEl.getBoundingClientRect()
        heroRect = { top: r.top + window.scrollY, bottom: r.bottom + window.scrollY, left: r.left, right: r.right }
      }
      // Check if hero is visible
      const scrollTop = window.scrollY
      const viewBottom = scrollTop + window.innerHeight
      isInHero = scrollTop < heroRect.bottom && viewBottom > heroRect.top
    }

    function draw() {
      ctx!.clearRect(0, 0, w, h)

      // Only render when hero is in viewport
      const scrollTop = window.scrollY
      if (!isInHero) {
        raf = requestAnimationFrame(draw)
        return
      }

      // Fade based on scroll
      const fadeProgress = Math.max(0, 1 - scrollTop / (heroRect.bottom - heroRect.top))
      if (fadeProgress <= 0) {
        raf = requestAnimationFrame(draw)
        return
      }
      ctx!.globalAlpha = fadeProgress * 0.75

      const mouseWorldY = mouse.y

      // Update points — repel from cursor, return to origin
      for (const p of points) {
        const dx = p.x - mouse.x
        const dy = p.y - mouseWorldY
        const dist = Math.sqrt(dx * dx + dy * dy)

        if (dist < MOUSE_RADIUS && dist > 0) {
          const force = (1 - dist / MOUSE_RADIUS) * REPEL_STRENGTH
          p.vx += (dx / dist) * force * 60
          p.vy += (dy / dist) * force * 60
        }

        // Spring back to origin
        p.vx += (p.originX - p.x) * RETURN_STRENGTH
        p.vy += (p.originY - p.y) * RETURN_STRENGTH

        // Damping
        p.vx *= 0.92
        p.vy *= 0.92

        p.x += p.vx
        p.y += p.vy
      }

      // Draw relative to scroll
      const offsetY = -scrollTop

      // Draw connections
      for (let i = 0; i < points.length; i++) {
        for (let j = i + 1; j < points.length; j++) {
          const dx = points[i].x - points[j].x
          const dy = points[i].y - points[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < CONNECT_DIST) {
            const alpha = (1 - dist / CONNECT_DIST) * 0.35

            // Brighten lines near the mouse
            const midX = (points[i].x + points[j].x) / 2
            const midY = (points[i].y + points[j].y) / 2
            const mouseDist = Math.sqrt((midX - mouse.x) ** 2 + (midY - mouseWorldY) ** 2)
            const mouseInfluence = Math.max(0, 1 - mouseDist / MOUSE_RADIUS)

            ctx!.beginPath()
            ctx!.moveTo(points[i].x, points[i].y + offsetY)
            ctx!.lineTo(points[j].x, points[j].y + offsetY)
            ctx!.strokeStyle = mouseInfluence > 0.1
              ? `rgba(124, 240, 255, ${alpha + mouseInfluence * 0.5})`
              : `rgba(154, 160, 174, ${alpha * 0.7})`
            ctx!.lineWidth = 0.6 + mouseInfluence * 1.2
            ctx!.stroke()
          }
        }
      }

      // Draw dots
      for (const p of points) {
        const dx = p.x - mouse.x
        const dy = p.y - mouseWorldY
        const mouseDist = Math.sqrt(dx * dx + dy * dy)
        const mouseInfluence = Math.max(0, 1 - mouseDist / MOUSE_RADIUS)
        const radius = 1.2 + mouseInfluence * 2.5

        ctx!.beginPath()
        ctx!.arc(p.x, p.y + offsetY, radius, 0, Math.PI * 2)
        ctx!.fillStyle = mouseInfluence > 0.1
          ? `rgba(124, 240, 255, ${0.6 + mouseInfluence * 0.4})`
          : `rgba(154, 160, 174, 0.35)`
        ctx!.fill()
      }

      ctx!.globalAlpha = 1
      raf = requestAnimationFrame(draw)
    }

    window.addEventListener("resize", resize, { passive: true })
    window.addEventListener("pointermove", onPointerMove, { passive: true })
    window.addEventListener("scroll", onScroll, { passive: true })

    resize()
    isInHero = true
    onScroll()
    raf = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener("resize", resize)
      window.removeEventListener("pointermove", onPointerMove)
      window.removeEventListener("scroll", onScroll)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 3,
        pointerEvents: "none",
        width: "100%",
        height: "100%",
      }}
    />
  )
}
