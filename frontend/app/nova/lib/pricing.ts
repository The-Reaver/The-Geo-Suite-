"use client";

/*
 * Fetches the real pricing tiers from the backend (GET /sales/pricing-tiers,
 * backed by backend/app/core/pricing.py) instead of hardcoding a second copy
 * here. 2026-08-20: this panel and sales_kit.py's HTML used to carry the
 * same three tiers independently, kept in sync by hand.
 */

import { getBrowserAccessToken } from "./supabaseBrowser";
import { fetchWithTimeout } from "./fetchWithTimeout";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export type PricingTier = {
  name: string;
  price: number;
  tag: string;
  popular: boolean;
  bullets: string[];
};

export type PricingResult =
  | { ok: true; tiers: PricingTier[]; publishThreshold: number }
  | { ok: false };

export async function fetchPricingTiers(): Promise<PricingResult> {
  try {
    const token = await getBrowserAccessToken();
    if (!token) return { ok: false };
    const res = await fetchWithTimeout(`${API_BASE_URL}/sales/pricing-tiers`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return { ok: false };
    const data = await res.json();
    if (!Array.isArray(data?.tiers)) return { ok: false };
    return { ok: true, tiers: data.tiers, publishThreshold: data.publish_threshold };
  } catch {
    return { ok: false };
  }
}
