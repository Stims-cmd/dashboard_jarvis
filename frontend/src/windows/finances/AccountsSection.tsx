import { useState, type FormEvent } from 'react'
import { api } from '../../api'
import { formatCents, formatRate, parseEuros } from './money'
import { BASE, formatDay, type Account } from './types'

interface Props {
  accounts: Account[]
  today: string
  onChange: () => void
}

function BalanceForm({ accounts, today, onChange }: Props) {
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? 0)
  const [day, setDay] = useState(today)
  const [amount, setAmount] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const cents = parseEuros(amount)
    if (cents === null) {
      setError('Montant invalide (ex. 1 234,56).')
      return
    }
    try {
      await api.post(`${BASE}/balances`, { account_id: accountId, day, amount_cents: cents })
      setAmount('')
      setError(null)
      onChange()
    } catch {
      setError('Enregistrement refusé (date future ou montant hors limites ?).')
    }
  }

  return (
    <form className="fin-form" onSubmit={submit}>
      <select value={accountId} onChange={(e) => setAccountId(Number(e.target.value))} aria-label="Compte">
        {accounts.map((a) => (
          <option key={a.id} value={a.id}>
            {a.label}
          </option>
        ))}
      </select>
      <input type="date" value={day} max={today} onChange={(e) => setDay(e.target.value)} required />
      <input
        inputMode="decimal"
        placeholder="Solde en €"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        required
      />
      <button type="submit">Ajouter le relevé</button>
      {error && <span className="error">{error}</span>}
    </form>
  )
}

function AccountEditor({ account, onChange }: { account: Account; onChange: () => void }) {
  const [label, setLabel] = useState(account.label)
  const [ceiling, setCeiling] = useState(
    account.ceiling_cents === null ? '' : String(account.ceiling_cents / 100).replace('.', ','),
  )
  const [closesOn, setClosesOn] = useState(account.closes_on ?? '')
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const ceilingCents = ceiling.trim() ? parseEuros(ceiling) : null
    if (ceiling.trim() && ceilingCents === null) {
      setError('Plafond invalide.')
      return
    }
    try {
      await api.put(`${BASE}/accounts/${account.id}`, {
        label,
        ceiling_cents: ceilingCents,
        closes_on: closesOn || null,
      })
      setError(null)
      onChange()
    } catch {
      setError('Modification refusée.')
    }
  }

  return (
    <details>
      <summary>Modifier</summary>
      <form className="fin-form" onSubmit={submit}>
        <input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={100} required aria-label="Libellé" />
        <input placeholder="Plafond en € (vide = aucun)" value={ceiling} onChange={(e) => setCeiling(e.target.value)} />
        <label>
          Échéance <input type="date" value={closesOn} onChange={(e) => setClosesOn(e.target.value)} />
        </label>
        <button type="submit">Enregistrer</button>
        {error && <span className="error">{error}</span>}
      </form>
    </details>
  )
}

export default function AccountsSection({ accounts, today, onChange }: Props) {
  return (
    <section>
      <h3>Comptes</h3>
      <ul className="fin-list">
        {accounts.map((account) => (
          <li key={account.id} className="fin-account">
            <div className="fin-row">
              <strong>{account.label}</strong>
              <span className="fin-amount">{formatCents(account.balance_cents)}</span>
            </div>
            <div className="fin-meta">
              {account.balance_day ? `Relevé du ${formatDay(account.balance_day)}` : 'Aucun relevé'}
              {account.rate_bp !== null && ` · taux ${formatRate(account.rate_bp)}`}
              {account.estimated_interest_cents !== null &&
                ` · ≈ ${formatCents(account.estimated_interest_cents)} d'intérêts sur 12 mois (estimation)`}
              {account.closes_on && ` · échéance ${formatDay(account.closes_on)}`}
            </div>
            {account.ceiling && account.ceiling_cents !== null && (
              <div className="fin-meta">
                <progress value={Math.min(account.ceiling.used_ratio, 1)} max={1} />
                <span className={account.ceiling.near_ceiling ? 'warning' : undefined}>
                  {' '}
                  Plafond {formatCents(account.ceiling_cents)} · reste {formatCents(account.ceiling.remaining_cents)}
                </span>
              </div>
            )}
            <AccountEditor account={account} onChange={onChange} />
          </li>
        ))}
      </ul>
      <BalanceForm accounts={accounts} today={today} onChange={onChange} />
    </section>
  )
}
