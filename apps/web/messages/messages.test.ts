/**
 * Every locale must have exactly the English keys, and every message must parse as ICU with the
 * same arguments, plural/select options and rich-text tags as English (so no runtime format errors).
 */
import { readFileSync } from "node:fs"

import { parse, TYPE, type MessageFormatElement } from "@formatjs/icu-messageformat-parser"
import { describe, expect, it } from "vitest"

type Tree = { [key: string]: string | Tree }

const load = (locale: string): Tree => JSON.parse(readFileSync(new URL(`./${locale}.json`, import.meta.url), "utf8"))

function flatten(tree: Tree, prefix = ""): Record<string, string> {
  return Object.fromEntries(
    Object.entries(tree).flatMap(([k, v]) =>
      typeof v === "string" ? [[`${prefix}${k}`, v]] : Object.entries(flatten(v, `${prefix}${k}.`)),
    ),
  )
}

function shape(elements: MessageFormatElement[], out: string[] = []): string[] {
  for (const el of elements) {
    if (el.type === TYPE.argument) out.push(`arg:${el.value}`)
    else if (el.type === TYPE.number || el.type === TYPE.date || el.type === TYPE.time) out.push(`${el.type}:${el.value}`)
    else if (el.type === TYPE.tag) {
      out.push(`tag:${el.value}`)
      shape(el.children, out)
    } else if (el.type === TYPE.plural || el.type === TYPE.select) {
      out.push(`${el.type === TYPE.plural ? "plural" : "select"}:${el.value}:${Object.keys(el.options).sort().join("|")}`)
      for (const option of Object.values(el.options)) shape(option.value, out)
    }
  }
  return out
}

const en = flatten(load("en"))
const signature = (message: string) => [...new Set(shape(parse(message)))].sort()

describe.each(["ko", "de"])("%s messages", (locale) => {
  const messages = flatten(load(locale))

  it("have exactly the English keys", () => {
    expect(Object.keys(messages).sort()).toEqual(Object.keys(en).sort())
  })

  it("keep the ICU structure of every English message", () => {
    const broken: string[] = []
    for (const [key, source] of Object.entries(en)) {
      try {
        if (JSON.stringify(signature(messages[key])) !== JSON.stringify(signature(source))) broken.push(key)
      } catch {
        broken.push(`${key} (does not parse)`)
      }
    }
    expect(broken).toEqual([])
  })
})

it("English messages all parse", () => {
  const failing = Object.entries(en).filter(([, m]) => {
    try {
      parse(m)
      return false
    } catch {
      return true
    }
  })
  expect(failing.map(([k]) => k)).toEqual([])
})
