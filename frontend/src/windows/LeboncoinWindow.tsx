import { useCallback, useState } from 'react'
import { UnauthorizedError } from '../api'
import AdsSection from './leboncoin/AdsSection'
import AnalysisSection from './leboncoin/AnalysisSection'
import SalesSection from './leboncoin/SalesSection'

type Tab = 'ads' | 'sales' | 'analysis'

export default function LeboncoinWindow() {
  const [tab, setTab] = useState<Tab>('ads')
  const [error, setError] = useState<string | null>(null)

  const onError = useCallback(
    (err: unknown) =>
      setError(err instanceof UnauthorizedError ? 'Session expirée : recharge la page.' : 'Chargement impossible.'),
    [],
  )

  if (error) return <p className="error">{error}</p>

  return (
    <div className="vc">
      <div className="lbc-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'ads'} onClick={() => setTab('ads')}>
          Annonces suivies
        </button>
        <button type="button" role="tab" aria-selected={tab === 'sales'} onClick={() => setTab('sales')}>
          Mes ventes
        </button>
        <button type="button" role="tab" aria-selected={tab === 'analysis'} onClick={() => setTab('analysis')}>
          Analyser
        </button>
      </div>
      {tab === 'ads' && <AdsSection onError={onError} />}
      {tab === 'sales' && <SalesSection onError={onError} />}
      {tab === 'analysis' && <AnalysisSection onError={onError} />}
    </div>
  )
}
