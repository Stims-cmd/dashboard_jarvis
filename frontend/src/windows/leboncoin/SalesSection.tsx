import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api } from '../../api'
import { formatCents, parseEuros } from '../finances/money'
import {
  BASE,
  CONDITIONS,
  day,
  isLeboncoinUrl,
  STATUSES,
  type Comparables,
  type Condition,
  type Item,
  type ItemInput,
  type ItemStatus,
} from './types'

const centsToInput = (cents: number | null) => (cents === null ? '' : (cents / 100).toFixed(2).replace('.', ','))

function toInput(item: Item): ItemInput {
  return {
    title: item.title,
    condition: item.condition,
    notes: item.notes,
    keywords: item.keywords,
    asking_price_cents: item.asking_price_cents,
    floor_price_cents: item.floor_price_cents,
    status: item.status,
    listed_on: item.listed_on,
    lower_after_days: item.lower_after_days,
  }
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // The clipboard API needs HTTPS (or localhost).
    window.alert('Copie impossible ici : sélectionne le texte à la main.')
  }
}

function ItemForm({ item, onSaved }: { item?: Item; onSaved: () => void }) {
  const [title, setTitle] = useState(item?.title ?? '')
  const [condition, setCondition] = useState<Condition>(item?.condition ?? 'bon')
  const [notes, setNotes] = useState(item?.notes ?? '')
  const [keywords, setKeywords] = useState(item?.keywords ?? '')
  const [asking, setAsking] = useState(centsToInput(item?.asking_price_cents ?? null))
  const [floor, setFloor] = useState(centsToInput(item?.floor_price_cents ?? null))
  const [status, setStatus] = useState<ItemStatus>(item?.status ?? 'draft')
  const [listedOn, setListedOn] = useState(item?.listed_on ?? '')
  const [lowerAfter, setLowerAfter] = useState(String(item?.lower_after_days ?? 14))
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const askingCents = parseEuros(asking)
    const floorCents = floor.trim() ? parseEuros(floor) : null
    if (askingCents === null || askingCents < 0 || (floor.trim() && floorCents === null)) {
      setError('Prix invalide.')
      return
    }
    if (floorCents !== null && floorCents > askingCents) {
      setError('Le prix plancher dépasse le prix demandé.')
      return
    }
    const body: ItemInput = {
      title,
      condition,
      notes,
      keywords,
      asking_price_cents: askingCents,
      floor_price_cents: floorCents,
      status,
      listed_on: listedOn || null,
      lower_after_days: Number(lowerAfter),
    }
    try {
      if (item) await api.put(`${BASE}/items/${item.id}`, body)
      else await api.post(`${BASE}/items`, body)
      setError(null)
      if (!item) {
        setTitle('')
        setNotes('')
        setKeywords('')
        setAsking('')
        setFloor('')
      }
      onSaved()
    } catch {
      setError('Objet refusé : vérifie les champs.')
    }
  }

  return (
    <form className="fin-form lbc-form" onSubmit={submit}>
      <input placeholder="Objet" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={100} required />
      <select value={condition} onChange={(e) => setCondition(e.target.value as Condition)} aria-label="État">
        {Object.entries(CONDITIONS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <textarea
        placeholder="Détails : défauts, accessoires, dimensions… (pas de coordonnées)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        maxLength={2000}
        rows={3}
      />
      <input
        placeholder="Mots-clés pour comparer (ex. vélo ville)"
        value={keywords}
        onChange={(e) => setKeywords(e.target.value)}
        maxLength={200}
      />
      <input inputMode="decimal" placeholder="Prix demandé en €" value={asking} onChange={(e) => setAsking(e.target.value)} required />
      <input inputMode="decimal" placeholder="Prix plancher en € (optionnel)" value={floor} onChange={(e) => setFloor(e.target.value)} />
      <select value={status} onChange={(e) => setStatus(e.target.value as ItemStatus)} aria-label="Statut">
        {Object.entries(STATUSES).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <label>
        Mis en vente le <input type="date" value={listedOn} onChange={(e) => setListedOn(e.target.value)} />
      </label>
      <label>
        Rappel de baisse après{' '}
        <input type="number" min={1} max={365} value={lowerAfter} onChange={(e) => setLowerAfter(e.target.value)} /> jours
      </label>
      <button type="submit">{item ? 'Enregistrer' : 'Ajouter'}</button>
      {error && <span className="error">{error}</span>}
    </form>
  )
}

function ComparablesPanel({ item }: { item: Item }) {
  const [data, setData] = useState<Comparables | null>(null)

  function load() {
    if (data === null) api.get<Comparables>(`${BASE}/items/${item.id}/comparables`).then(setData).catch(() => {})
  }

  return (
    <details onToggle={load}>
      <summary>Annonces comparables</summary>
      {data === null ? (
        <p className="placeholder">Chargement…</p>
      ) : data.keywords.length === 0 ? (
        <p className="placeholder">Ajoute des mots-clés à l'objet pour trouver des annonces comparables.</p>
      ) : data.ads.length === 0 ? (
        <p className="placeholder">Aucune annonce collectée ne contient « {data.keywords.join(' ')} ».</p>
      ) : (
        <>
          <p className="fin-meta">
            {data.count} annonces avec prix · médiane {formatCents(data.median_cents)} · de {formatCents(data.min_cents)}{' '}
            à {formatCents(data.max_cents)}
          </p>
          <ul className="vc-list">
            {data.ads.map((ad) => (
              <li key={ad.url} className="vc-item fin-meta">
                {isLeboncoinUrl(ad.url) ? (
                  <a href={ad.url} target="_blank" rel="noreferrer noopener">
                    {ad.title}
                  </a>
                ) : (
                  ad.title
                )}{' '}
                · {ad.price_cents === null ? 'sans prix' : formatCents(ad.price_cents)} · {ad.location}
              </li>
            ))}
          </ul>
        </>
      )}
    </details>
  )
}

function ItemCard({ item, onChange }: { item: Item; onChange: () => void }) {
  const [editing, setEditing] = useState(false)
  const [drafting, setDrafting] = useState(false)
  const reminder = item.reminder

  async function draft() {
    setDrafting(true)
    try {
      await api.post(`${BASE}/items/${item.id}/draft`, {})
      onChange()
    } finally {
      setDrafting(false)
    }
  }

  async function recordDrop(cents: number) {
    if (!window.confirm(`As-tu baissé le prix à ${formatCents(cents)} sur Leboncoin ?`)) return
    await api.put(`${BASE}/items/${item.id}`, { ...toInput(item), asking_price_cents: cents })
    onChange()
  }

  async function remove() {
    if (!window.confirm(`Supprimer « ${item.title} » ?`)) return
    await api.del(`${BASE}/items/${item.id}`)
    onChange()
  }

  return (
    <li className="fin-account">
      <div className="fin-row">
        <strong>{item.title}</strong>
        <span className="fin-amount">{formatCents(item.asking_price_cents)}</span>
      </div>
      <div className="fin-meta">
        {STATUSES[item.status]}
        {item.listed_on && ` depuis le ${day(item.listed_on)}`} · {CONDITIONS[item.condition]}
        {item.floor_price_cents !== null && ` · plancher ${formatCents(item.floor_price_cents)}`}
        {item.price_history.length > 1 &&
          ` · prix : ${item.price_history.map(([, cents]) => formatCents(cents)).join(' → ')}`}
      </div>
      {reminder?.due && (
        <div className="lbc-reminder">
          {reminder.suggested_cents !== null ? (
            <>
              Pas vendu depuis le {day(reminder.since)} : baisser à {formatCents(reminder.suggested_cents)} ?{' '}
              <button type="button" className="link-button" onClick={() => recordDrop(reminder.suggested_cents!)}>
                j'ai baissé le prix
              </button>
            </>
          ) : (
            <>Pas vendu depuis le {day(reminder.since)}, et déjà au prix plancher.</>
          )}
        </div>
      )}

      {item.draft_title && item.draft_body && (
        <div className="lbc-draft">
          <div className="fin-meta">
            Brouillon ({item.draft_source === 'claude' ? 'rédigé par Claude' : 'gabarit'}) — à relire avant de publier
          </div>
          <div className="fin-row">
            <strong>{item.draft_title}</strong>
            <button type="button" className="link-button" onClick={() => copy(item.draft_title!)}>
              copier le titre
            </button>
          </div>
          <p className="lbc-draft-body">{item.draft_body}</p>
          <button type="button" className="link-button" onClick={() => copy(item.draft_body!)}>
            copier la description
          </button>
        </div>
      )}

      <div className="fin-meta lbc-actions">
        <button type="button" className="link-button" onClick={draft} disabled={drafting}>
          {drafting ? 'rédaction…' : item.draft_body ? 'réécrire le brouillon' : 'rédiger le brouillon'}
        </button>
        <button type="button" className="link-button" onClick={() => setEditing(!editing)}>
          {editing ? 'fermer' : 'modifier'}
        </button>
        <button type="button" className="link-button" onClick={remove}>
          supprimer
        </button>
      </div>
      {editing && (
        <ItemForm
          item={item}
          onSaved={() => {
            setEditing(false)
            onChange()
          }}
        />
      )}
      <ComparablesPanel item={item} />
    </li>
  )
}

export default function SalesSection({ onError }: { onError: (err: unknown) => void }) {
  const [items, setItems] = useState<Item[] | null>(null)

  const reload = useCallback(() => {
    api.get<Item[]>(`${BASE}/items`).then(setItems).catch(onError)
  }, [onError])

  useEffect(reload, [reload])

  if (items === null) return <p className="placeholder">Chargement…</p>

  return (
    <div className="fin">
      {items.length === 0 && <p className="placeholder">Aucun objet à vendre pour l'instant.</p>}
      <ul className="fin-list">
        {items.map((item) => (
          <ItemCard key={item.id} item={item} onChange={reload} />
        ))}
      </ul>
      <details>
        <summary>Nouvel objet à vendre</summary>
        <ItemForm onSaved={reload} />
      </details>
      <p className="disclaimer">
        Jarvis ne publie rien et n'envoie aucun message : relis le brouillon, copie-le et publie-le toi-même. N'écris
        pas tes coordonnées dans les détails : seule la description de l'objet est envoyée à Claude, et les e-mails et
        numéros de téléphone en sont retirés.
      </p>
    </div>
  )
}
