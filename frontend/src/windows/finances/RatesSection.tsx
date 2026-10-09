import { useState, type FormEvent } from 'react'
import { api } from '../../api'
import { formatRate, parseRate } from './money'
import { BASE, formatDay, PRODUCT_LABELS, type RateInfo } from './types'

function RateForm({ rate, today, onChange }: { rate: RateInfo; today: string; onChange: () => void }) {
  const [value, setValue] = useState('')
  const [validFrom, setValidFrom] = useState(today)
  const [source, setSource] = useState(rate.official_link)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const bp = parseRate(value)
    if (bp === null) {
      setError('Taux invalide (ex. 1,70).')
      return
    }
    try {
      await api.post(`${BASE}/rates`, {
        product: rate.product,
        rate_bp: bp,
        valid_from: validFrom,
        source_url: source,
        checked_on: today,
      })
      setValue('')
      setError(null)
      onChange()
    } catch {
      setError('Refusé : taux entre 0 et 20 %, source en https://.')
    }
  }

  return (
    <details>
      <summary>Saisir le taux vérifié</summary>
      <form className="fin-form" onSubmit={submit}>
        <input inputMode="decimal" placeholder="Taux en %" value={value} onChange={(e) => setValue(e.target.value)} required />
        <label>
          En vigueur depuis <input type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} required />
        </label>
        <input type="url" value={source} onChange={(e) => setSource(e.target.value)} aria-label="Source" required />
        <button type="submit">Enregistrer</button>
        {error && <span className="error">{error}</span>}
      </form>
    </details>
  )
}

export default function RatesSection({
  rates,
  today,
  onChange,
}: {
  rates: RateInfo[]
  today: string
  onChange: () => void
}) {
  return (
    <section>
      <h3>Taux</h3>
      <ul className="fin-list">
        {rates.map((rate) => (
          <li key={rate.product} className="fin-account">
            <div className="fin-row">
              <strong>{PRODUCT_LABELS[rate.product]}</strong>
              <span>{formatRate(rate.rate_bp)}</span>
            </div>
            <div className="fin-meta">
              {rate.checked_on
                ? `Vérifié le ${formatDay(rate.checked_on)}, en vigueur depuis le ${formatDay(rate.valid_from)}`
                : 'Non renseigné'}
              {' · '}
              <a href={rate.official_link} target="_blank" rel="noreferrer noopener">
                source officielle
              </a>
            </div>
            {rate.needs_check && <div className="warning">À vérifier : révision officielle depuis le dernier contrôle.</div>}
            {rate.below_livret_a && (
              <div className="warning">Inférieur au taux du Livret A : impossible pour un Livret Jeune, à vérifier.</div>
            )}
            <RateForm rate={rate} today={today} onChange={onChange} />
          </li>
        ))}
      </ul>
    </section>
  )
}
