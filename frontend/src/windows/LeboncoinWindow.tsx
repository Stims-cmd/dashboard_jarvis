import { useEffect, useState } from 'react'
import { api, UnauthorizedError } from '../api'

const BASE = '/api/modules/leboncoin'

interface Ad {
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

interface Search {
  name: string
  ads: number
}

interface Status {
  last_success_at: string | null
  last_run_status: string | null
  stale: boolean
  imap_configured: boolean
  total_ads: number
}

const day = (iso: string) => new Date(iso).toLocaleDateString('fr-FR')
const euros = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })
const price = (cents: number | null) => (cents === null ? 'prix non indiqué' : euros.format(cents / 100))

// Links come from emails: only https links to Leboncoin itself are clickable.
function isLeboncoinUrl(href: string) {
  try {
    const url = new URL(href)
    return url.protocol === 'https:' && (url.hostname === 'leboncoin.fr' || url.hostname.endsWith('.leboncoin.fr'))
  } catch {
    return false
  }
}

function AdItem({ ad }: { ad: Ad }) {
  const prices = ad.price_history.map(([, cents]) => cents).filter((c): c is number => c !== null)
  const first = prices[0]
  const dropped = first !== undefined && ad.price_cents !== null && ad.price_cents < first
  return (
    <li className="vc-item">
      <div className="vc-item-head">
        {isLeboncoinUrl(ad.url) ? (
          <a href={ad.url} target="_blank" rel="noreferrer noopener">
            {ad.title}
          </a>
        ) : (
          <span>{ad.title}</span>
        )}
        <span className="badge">{price(ad.price_cents)}</span>
        {dropped && <span className="badge">baisse : {price(first)} → {price(ad.price_cents)}</span>}
      </div>
      <div className="vc-item-product">
        {ad.location} · {ad.search_name} · vue le {day(ad.first_seen_at)}
      </div>
    </li>
  )
}

export default function LeboncoinWindow() {
  const [status, setStatus] = useState<Status | null>(null)
  const [searches, setSearches] = useState<Search[]>([])
  const [search, setSearch] = useState('')
  const [ads, setAds] = useState<Ad[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const onError = (err: unknown) =>
    setError(err instanceof UnauthorizedError ? 'Session expirée : recharge la page.' : 'Chargement impossible.')

  useEffect(() => {
    Promise.all([api.get<Status>(`${BASE}/status`), api.get<Search[]>(`${BASE}/searches`)])
      .then(([s, list]) => {
        setStatus(s)
        setSearches(list)
      })
      .catch(onError)
  }, [])

  useEffect(() => {
    const query = search ? `?search=${encodeURIComponent(search)}` : ''
    api.get<Ad[]>(`${BASE}/ads${query}`).then(setAds).catch(onError)
  }, [search])

  if (error) return <p className="error">{error}</p>
  if (!status) return <p className="placeholder">Chargement…</p>

  return (
    <div className="vc">
      <div className="vc-status">
        <span className={status.stale ? 'warning' : undefined}>
          {status.last_success_at
            ? `Dernière lecture des alertes : ${new Date(status.last_success_at).toLocaleString('fr-FR')}`
            : 'Aucune collecte réussie'}
        </span>
        {!status.imap_configured && <span className="warning">boîte IMAP non configurée (.env)</span>}
        <span>{status.total_ads} annonces</span>
      </div>

      {searches.length > 1 && (
        <label>
          Recherche :{' '}
          <select value={search} onChange={(e) => setSearch(e.target.value)}>
            <option value="">toutes</option>
            {searches.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name} ({s.ads})
              </option>
            ))}
          </select>
        </label>
      )}

      {ads === null ? (
        <p className="placeholder">Chargement…</p>
      ) : ads.length === 0 ? (
        <p className="placeholder">
          Aucune annonce pour l'instant. Les annonces arrivent avec les alertes e-mail de tes recherches
          sauvegardées.
        </p>
      ) : (
        <ul className="vc-list">
          {ads.map((ad) => (
            <AdItem key={ad.id} ad={ad} />
          ))}
        </ul>
      )}
      <p className="disclaimer">
        Source : uniquement les alertes e-mail de tes recherches sauvegardées. Aucune requête n'est envoyée à
        Leboncoin et aucune image n'est chargée.
      </p>
    </div>
  )
}
