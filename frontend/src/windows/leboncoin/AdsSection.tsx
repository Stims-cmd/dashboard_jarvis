import { useEffect, useState } from 'react'
import { api } from '../../api'
import { formatCents } from '../finances/money'
import { BASE, day, isLeboncoinUrl, type Ad, type Search, type Status } from './types'

const price = (cents: number | null) => (cents === null ? 'prix non indiqué' : formatCents(cents))

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

export default function AdsSection({ onError }: { onError: (err: unknown) => void }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [searches, setSearches] = useState<Search[]>([])
  const [search, setSearch] = useState('')
  const [ads, setAds] = useState<Ad[] | null>(null)

  useEffect(() => {
    Promise.all([api.get<Status>(`${BASE}/status`), api.get<Search[]>(`${BASE}/searches`)])
      .then(([s, list]) => {
        setStatus(s)
        setSearches(list)
      })
      .catch(onError)
  }, [onError])

  useEffect(() => {
    const query = search ? `?search=${encodeURIComponent(search)}` : ''
    api.get<Ad[]>(`${BASE}/ads${query}`).then(setAds).catch(onError)
  }, [search, onError])

  if (!status) return <p className="placeholder">Chargement…</p>

  return (
    <>
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
    </>
  )
}
