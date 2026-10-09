import { useState, type FormEvent } from 'react'
import { api } from '../../api'
import { formatCents, parseEuros } from './money'
import { BASE, formatDay, type Account, type Goal } from './types'

function GoalForm({ accounts, onChange }: { accounts: Account[]; onChange: () => void }) {
  const [label, setLabel] = useState('')
  const [target, setTarget] = useState('')
  const [deadline, setDeadline] = useState('')
  const [accountId, setAccountId] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const cents = parseEuros(target)
    if (cents === null || cents <= 0) {
      setError('Montant cible invalide.')
      return
    }
    try {
      await api.post(`${BASE}/goals`, {
        label,
        target_cents: cents,
        deadline: deadline || null,
        account_id: accountId ? Number(accountId) : null,
      })
      setLabel('')
      setTarget('')
      setDeadline('')
      setError(null)
      onChange()
    } catch {
      setError('Objectif refusé.')
    }
  }

  return (
    <details>
      <summary>Nouvel objectif</summary>
      <form className="fin-form" onSubmit={submit}>
        <input placeholder="Nom" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={100} required />
        <input inputMode="decimal" placeholder="Montant cible en €" value={target} onChange={(e) => setTarget(e.target.value)} required />
        <label>
          Échéance <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
        </label>
        <select value={accountId} onChange={(e) => setAccountId(e.target.value)} aria-label="Compte suivi">
          <option value="">Tous les livrets</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.label}
            </option>
          ))}
        </select>
        <button type="submit">Créer</button>
        {error && <span className="error">{error}</span>}
      </form>
    </details>
  )
}

export default function GoalsSection({
  goals,
  accounts,
  onChange,
}: {
  goals: Goal[]
  accounts: Account[]
  onChange: () => void
}) {
  const accountLabel = (id: number | null) =>
    id === null ? 'tous les livrets' : (accounts.find((a) => a.id === id)?.label ?? '?')

  async function remove(goal: Goal) {
    if (!window.confirm(`Supprimer l'objectif « ${goal.label} » ?`)) return
    await api.del(`${BASE}/goals/${goal.id}`)
    onChange()
  }

  return (
    <section>
      <h3>Objectifs d'épargne</h3>
      {goals.length === 0 && <p className="placeholder">Aucun objectif.</p>}
      <ul className="fin-list">
        {goals.map((goal) => (
          <li key={goal.id} className="fin-account">
            <div className="fin-row">
              <strong>{goal.label}</strong>
              <span>
                {formatCents(goal.current_cents)} / {formatCents(goal.target_cents)}
              </span>
            </div>
            <progress value={goal.ratio} max={1} />
            <div className="fin-meta">
              Suivi : {accountLabel(goal.account_id)}
              {goal.remaining_cents > 0 ? ` · reste ${formatCents(goal.remaining_cents)}` : ' · atteint'}
              {goal.deadline && ` · échéance ${formatDay(goal.deadline)}`}
              {goal.monthly_effort_cents !== null && ` · ${formatCents(goal.monthly_effort_cents)} par mois`}
              {' · '}
              <button type="button" className="link-button" onClick={() => remove(goal)}>
                supprimer
              </button>
            </div>
          </li>
        ))}
      </ul>
      <GoalForm accounts={accounts} onChange={onChange} />
    </section>
  )
}
