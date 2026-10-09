import { useCallback, useEffect, useState } from 'react'
import { api, UnauthorizedError } from '../api'
import AccountsSection from './finances/AccountsSection'
import GoalsSection from './finances/GoalsSection'
import RatesSection from './finances/RatesSection'
import { BASE, type Overview } from './finances/types'

export default function FinancesWindow() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(() => {
    api
      .get<Overview>(`${BASE}/overview`)
      .then((data) => {
        setOverview(data)
        setError(null)
      })
      .catch((err: unknown) =>
        setError(err instanceof UnauthorizedError ? 'Session expirée : recharge la page.' : 'Chargement impossible.'),
      )
  }, [])

  useEffect(reload, [reload])

  if (error) return <p className="error">{error}</p>
  if (!overview) return <p className="placeholder">Chargement…</p>

  return (
    <div className="fin">
      <p className="disclaimer fin-disclaimer">{overview.disclaimer}</p>
      <AccountsSection accounts={overview.accounts} today={overview.today} onChange={reload} />
      <RatesSection rates={overview.rates} today={overview.today} onChange={reload} />
      <GoalsSection goals={overview.goals} accounts={overview.accounts} onChange={reload} />
    </div>
  )
}
