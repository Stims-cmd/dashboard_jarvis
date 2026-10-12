export const BASE = '/api/modules/leboncoin'

export interface Ad {
  id: number
  ad_id: string
  search_name: string
  title: string
  price_cents: number | null
  location: string
  url: string
  price_history: [string, number | null][]
  first_seen_at: string
  last_seen_at: string
}

export interface Search {
  name: string
  ads: number
}

export interface Status {
  last_success_at: string | null
  last_run_status: string | null
  stale: boolean
  imap_configured: boolean
  total_ads: number
}

export type Condition = 'neuf' | 'tres_bon' | 'bon' | 'correct' | 'pieces'
export type ItemStatus = 'draft' | 'listed' | 'sold' | 'withdrawn'

export interface ItemInput {
  title: string
  condition: Condition
  notes: string
  keywords: string
  asking_price_cents: number
  floor_price_cents: number | null
  status: ItemStatus
  listed_on: string | null
  lower_after_days: number
}

export interface Item extends ItemInput {
  id: number
  price_history: [string, number][]
  draft_title: string | null
  draft_body: string | null
  draft_source: 'claude' | 'template' | null
  reminder: { due: boolean; since: string; suggested_cents: number | null; at_floor: boolean } | null
  updated_at: string
}

export interface Comparables {
  keywords: string[]
  count: number
  min_cents: number | null
  median_cents: number | null
  max_cents: number | null
  ads: { title: string; price_cents: number | null; location: string; url: string; first_seen_at: string }[]
}

export const CONDITIONS: Record<Condition, string> = {
  neuf: 'Neuf',
  tres_bon: 'Très bon état',
  bon: 'Bon état',
  correct: 'État correct',
  pieces: 'Pour pièces',
}

export const STATUSES: Record<ItemStatus, string> = {
  draft: 'en préparation',
  listed: 'en vente',
  sold: 'vendu',
  withdrawn: 'retiré',
}

export const day = (iso: string) => new Date(iso).toLocaleDateString('fr-FR')

// Links come from emails: only https links to Leboncoin itself are clickable.
export function isLeboncoinUrl(href: string) {
  try {
    const url = new URL(href)
    return url.protocol === 'https:' && (url.hostname === 'leboncoin.fr' || url.hostname.endsWith('.leboncoin.fr'))
  } catch {
    return false
  }
}
