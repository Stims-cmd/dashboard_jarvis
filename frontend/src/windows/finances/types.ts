export const BASE = '/api/modules/finances'

export interface Account {
  id: number
  label: string
  kind: 'livret_a' | 'livret_jeune' | 'courant' | 'pro'
  ceiling_cents: number | null
  closes_on: string | null
  balance_cents: number | null
  balance_day: string | null
  ceiling: { remaining_cents: number; used_ratio: number; near_ceiling: boolean } | null
  rate_bp: number | null
  estimated_interest_cents: number | null
}

export interface RateInfo {
  product: 'livret_a' | 'livret_jeune'
  rate_bp: number | null
  valid_from: string | null
  source_url: string | null
  checked_on: string | null
  needs_check: boolean
  below_livret_a: boolean
  official_link: string
}

export interface Goal {
  id: number
  label: string
  target_cents: number
  deadline: string | null
  account_id: number | null
  current_cents: number
  remaining_cents: number
  ratio: number
  monthly_effort_cents: number | null
}

export interface Overview {
  today: string
  accounts: Account[]
  rates: RateInfo[]
  goals: Goal[]
  disclaimer: string
}

export const PRODUCT_LABELS: Record<RateInfo['product'], string> = {
  livret_a: 'Livret A',
  livret_jeune: 'Livret Jeune',
}

export const formatDay = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '—')
