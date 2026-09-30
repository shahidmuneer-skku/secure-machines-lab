import { notFound } from "next/navigation"
import { Suspense } from "react"

import { MockCheckout } from "@/components/billing/billing-return"

/** Development-only stand-in for a hosted checkout page. */
export default function MockCheckoutPage() {
  if (process.env.NODE_ENV === "production") notFound()
  return <Suspense><MockCheckout /></Suspense>
}
