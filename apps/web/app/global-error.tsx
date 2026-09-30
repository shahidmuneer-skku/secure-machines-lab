"use client"

// Replaces the root layout when it fails, so it cannot use app styles, fonts or translations.
export default function GlobalError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, minHeight: "100vh", display: "grid", placeItems: "center", background: "#07080b",
        color: "#e6edf3", fontFamily: "system-ui, -apple-system, 'Segoe UI', 'Noto Sans KR', sans-serif" }}>
        <title>Secure Machines Lab</title>
        <main style={{ maxWidth: 440, padding: 24, textAlign: "center" }}>
          <p style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, letterSpacing: "0.2em", color: "#22d3ee" }}>
            SECURE MACHINES LAB
          </p>
          <h1 style={{ fontSize: 22, margin: "12px 0" }}>Something went wrong · 문제가 발생했습니다</h1>
          <p style={{ fontSize: 14, lineHeight: 1.6, color: "#9aa4b2" }}>
            The page could not be displayed. Please try again in a moment.
          </p>
          {error.digest && <p style={{ fontFamily: "ui-monospace, monospace", fontSize: 12, color: "#9aa4b2" }}>
            Reference: {error.digest}</p>}
          <button onClick={() => retry()} style={{ marginTop: 16, padding: "10px 18px", borderRadius: 8, border: 0,
            background: "#22d3ee", color: "#07080b", fontWeight: 600, cursor: "pointer" }}>Try again · 다시 시도</button>
        </main>
      </body>
    </html>
  )
}
