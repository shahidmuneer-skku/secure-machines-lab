"use client"

import { useEffect, useRef } from "react"

const VERTEX_SHADER = `
  attribute vec2 p;
  void main(){ gl_Position = vec4(p, 0.0, 1.0); }
`

const FRAGMENT_SHADER = `
  precision highp float;
  uniform vec2 uRes;
  uniform float uTime;
  uniform vec2 uMouse;
  uniform vec3 uA;
  uniform vec3 uB;
  uniform vec3 uC;
  uniform float uIntensity;

  float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453); }
  float noise(vec2 p){
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    vec2 u = f*f*(3.0-2.0*f);
    return mix(a,b,u.x) + (c-a)*u.y*(1.0-u.x) + (d-b)*u.x*u.y;
  }
  float fbm(vec2 p){
    float v = 0.0; float a = 0.5;
    for(int i=0;i<5;i++){ v += a*noise(p); p *= 2.02; a *= 0.5; }
    return v;
  }

  void main(){
    vec2 uv = (gl_FragCoord.xy - 0.5*uRes.xy) / min(uRes.x, uRes.y);
    vec2 m = (uMouse - 0.5*uRes.xy) / min(uRes.x, uRes.y);

    float t = uTime * 0.08;
    vec2 q = vec2(fbm(uv*1.3 + t), fbm(uv*1.3 - t + 4.0));
    vec2 r = vec2(
      fbm(uv*1.8 + q*1.6 + vec2(1.7, 9.2) + t*1.3),
      fbm(uv*1.8 + q*1.6 + vec2(8.3, 2.8) - t*1.1)
    );

    float field = fbm(uv*1.6 + r*1.7 + m*0.35);

    float blob1 = smoothstep(0.35, 0.75, field);
    float blob2 = smoothstep(0.55, 0.95, field + 0.1*sin(uTime*0.3 + r.x*3.14));

    vec3 col = vec3(0.0);

    vec3 glow = mix(uA, uC, smoothstep(0.0, 1.0, r.y));
    col += glow * blob1 * 0.42 * uIntensity;

    float mdist = length(uv - m);
    float spot = smoothstep(0.7, 0.0, mdist);
    col += uB * blob2 * 0.28 * uIntensity;
    col += uB * spot * 0.22 * uIntensity;

    col += vec3((hash(gl_FragCoord.xy*0.3 + t) - 0.5) * 0.012);

    float v = 1.0 - smoothstep(0.3, 1.2, length(uv));
    col *= mix(0.6, 1.0, v);

    col = max(col, vec3(0.0));

    gl_FragColor = vec4(col, 1.0);
  }
`

function hexToRgb(hex: string): [number, number, number] {
  hex = hex.replace("#", "")
  if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("")
  const n = parseInt(hex, 16)
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]
}

export default function LiquidCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const gl = canvas.getContext("webgl", { premultipliedAlpha: false, antialias: false })
    if (!gl) return

    function compile(type: number, src: string) {
      const s = gl!.createShader(type)!
      gl!.shaderSource(s, src)
      gl!.compileShader(s)
      return s
    }

    const vs = compile(gl.VERTEX_SHADER, VERTEX_SHADER)
    const fs = compile(gl.FRAGMENT_SHADER, FRAGMENT_SHADER)
    const prog = gl.createProgram()!
    gl.attachShader(prog, vs)
    gl.attachShader(prog, fs)
    gl.linkProgram(prog)
    gl.useProgram(prog)

    const buf = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buf)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW)
    const loc = gl.getAttribLocation(prog, "p")
    gl.enableVertexAttribArray(loc)
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0)

    const uRes = gl.getUniformLocation(prog, "uRes")
    const uTime = gl.getUniformLocation(prog, "uTime")
    const uMouse = gl.getUniformLocation(prog, "uMouse")
    const uA = gl.getUniformLocation(prog, "uA")
    const uB = gl.getUniformLocation(prog, "uB")
    const uC = gl.getUniformLocation(prog, "uC")
    const uIntensity = gl.getUniformLocation(prog, "uIntensity")

    let w = 0, h = 0
    const dpr = Math.min(window.devicePixelRatio || 1, 1.6)

    function resize() {
      const vw = window.innerWidth
      const vh = window.innerHeight
      w = Math.floor(vw * dpr)
      h = Math.floor(vh * dpr)
      canvas!.width = w
      canvas!.height = h
      gl!.viewport(0, 0, w, h)
    }
    window.addEventListener("resize", resize, { passive: true })
    resize()

    const mouse = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.5 }
    const target = { x: mouse.x, y: mouse.y }

    function onPointerMove(e: PointerEvent) { target.x = e.clientX; target.y = e.clientY }
    window.addEventListener("pointermove", onPointerMove, { passive: true })

    const faceBg = document.getElementById("face-bg")
    let scrollFade = 1

    function updateScrollFade() {
      const y = window.scrollY
      const vh = window.innerHeight
      scrollFade = Math.max(0.2, 1 - y / (vh * 1.2))
      if (faceBg) {
        const faceFade = Math.max(0.12, 0.58 - (y / (vh * 0.9)) * 0.58)
        faceBg.style.opacity = faceFade.toFixed(3)
      }
    }
    window.addEventListener("scroll", updateScrollFade, { passive: true })
    updateScrollFade()

    const palA = hexToRgb("#0ea5e9")
    const palB = hexToRgb("#6366f1")
    const palC = hexToRgb("#a78bfa")

    const t0 = performance.now()
    let raf: number

    function frame() {
      mouse.x += (target.x - mouse.x) * 0.06
      mouse.y += (target.y - mouse.y) * 0.06

      gl!.uniform2f(uRes, w, h)
      gl!.uniform1f(uTime, (performance.now() - t0) / 1000)
      gl!.uniform2f(uMouse, mouse.x * dpr, (window.innerHeight - mouse.y) * dpr)
      gl!.uniform3f(uA, palA[0], palA[1], palA[2])
      gl!.uniform3f(uB, palB[0], palB[1], palB[2])
      gl!.uniform3f(uC, palC[0], palC[1], palC[2])
      gl!.uniform1f(uIntensity, 1.0 * scrollFade)

      gl!.drawArrays(gl!.TRIANGLES, 0, 6)
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener("resize", resize)
      window.removeEventListener("pointermove", onPointerMove)
      window.removeEventListener("scroll", updateScrollFade)
    }
  }, [])

  return <canvas ref={canvasRef} className="liquid-canvas" />
}
