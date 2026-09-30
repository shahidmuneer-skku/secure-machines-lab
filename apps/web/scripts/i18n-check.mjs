// Verifies every message key exists in every locale (run in CI: node scripts/i18n-check.mjs).
import { readFileSync } from "node:fs"

const locales = ["en", "ko", "de"]
const flatten = (obj, prefix = "") =>
  Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? flatten(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  )
const sets = Object.fromEntries(
  locales.map((l) => [l, new Set(flatten(JSON.parse(readFileSync(new URL(`../messages/${l}.json`, import.meta.url)))))]),
)
let failed = false
for (const l of locales.slice(1)) {
  const missing = [...sets.en].filter((k) => !sets[l].has(k))
  const extra = [...sets[l]].filter((k) => !sets.en.has(k))
  if (missing.length || extra.length) {
    failed = true
    console.error(`[${l}] missing ${missing.length}: ${missing.slice(0, 20).join(", ")}`)
    if (extra.length) console.error(`[${l}] extra ${extra.length}: ${extra.slice(0, 20).join(", ")}`)
  }
}
console.log(failed ? "i18n check failed" : `i18n OK (${sets.en.size} keys × ${locales.length} locales)`)
process.exit(failed ? 1 : 0)
