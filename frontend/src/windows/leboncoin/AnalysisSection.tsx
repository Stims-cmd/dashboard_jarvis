import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api } from '../../api'
import { formatCents } from '../finances/money'
import { BASE, day, isHttpsUrl, VERDICTS, type Analysis } from './types'

const STATUS_MARKS = { ok: '✓', ko: '✗', inconnu: '?' } as const

function AnalysisForm({ onDone }: { onDone: (analysis: Analysis) => void }) {
  const [text, setText] = useState('')
  const [criteria, setCriteria] = useState('')
  const [keywords, setKeywords] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setRunning(true)
    setError(null)
    try {
      const analysis = await api.post<Analysis>(`${BASE}/analyses`, { text, criteria, keywords })
      setText('')
      setKeywords('')
      onDone(analysis)
    } catch {
      setError('Analyse impossible : vérifie le texte (8 000 caractères maximum).')
    } finally {
      setRunning(false)
    }
  }

  return (
    <form className="fin-form lbc-form" onSubmit={submit}>
      <textarea
        placeholder="Colle ici l'annonce : titre, prix, description, lieu…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={8000}
        rows={6}
        required
      />
      <textarea
        placeholder="Tes critères (ex. budget 300 €, moins de 3 ans, pas de rayure, taille M)"
        value={criteria}
        onChange={(e) => setCriteria(e.target.value)}
        maxLength={1000}
        rows={2}
      />
      <input
        placeholder="Mots-clés pour comparer (optionnel, sinon pris dans le titre)"
        value={keywords}
        onChange={(e) => setKeywords(e.target.value)}
        maxLength={200}
      />
      <button type="submit" disabled={running}>
        {running ? 'Analyse en cours… (jusqu’à une minute)' : 'Analyser'}
      </button>
      {error && <span className="error">{error}</span>}
    </form>
  )
}

function AnalysisCard({ analysis, open, onDelete }: { analysis: Analysis; open: boolean; onDelete: () => void }) {
  const { result, comparables } = analysis

  async function remove() {
    if (!window.confirm(`Supprimer l'analyse de « ${analysis.title} » ?`)) return
    await api.del(`${BASE}/analyses/${analysis.id}`)
    onDelete()
  }

  return (
    <li className="fin-account">
      <details open={open}>
        <summary className="fin-row">
          <strong>{analysis.title}</strong>
          <span>
            {result && <span className={`badge lbc-verdict-${result.verdict}`}>{VERDICTS[result.verdict]}</span>}{' '}
            {analysis.price_cents !== null && <span className="fin-amount">{formatCents(analysis.price_cents)}</span>}
          </span>
        </summary>
        <div className="fin-meta">
          {day(analysis.created_at)} · {analysis.source === 'claude' ? 'analyse Claude' : 'analyse locale (sans Claude)'}
        </div>

        {result && <p className="lbc-draft-body">{result.resume}</p>}

        {analysis.signals.length > 0 && (
          <div className="lbc-reminder">
            Signaux d'alerte détectés :
            <ul className="lbc-analysis-list">
              {analysis.signals.map((signal) => (
                <li key={signal}>{signal}</li>
              ))}
            </ul>
          </div>
        )}

        {result && (
          <>
            {result.criteres.length > 0 && (
              <>
                <h4 className="lbc-analysis-title">Tes critères</h4>
                <ul className="lbc-analysis-list">
                  {result.criteres.map((check) => (
                    <li key={check.critere} className={`lbc-check-${check.statut}`}>
                      <span aria-label={check.statut}>{STATUS_MARKS[check.statut]}</span> {check.critere}
                      {check.detail && <span className="fin-meta"> — {check.detail}</span>}
                    </li>
                  ))}
                </ul>
              </>
            )}
            <h4 className="lbc-analysis-title">Fiabilité du modèle</h4>
            <p className="lbc-draft-body">{result.fiabilite || 'Rien trouvé.'}</p>
            <h4 className="lbc-analysis-title">Risque d'arnaque</h4>
            <p className="lbc-draft-body">{result.arnaque || 'Rien à signaler.'}</p>
            <h4 className="lbc-analysis-title">Prix</h4>
            <p className="lbc-draft-body">{result.prix || 'Pas d’avis.'}</p>
            {result.questions_vendeur.length > 0 && (
              <>
                <h4 className="lbc-analysis-title">Questions à poser au vendeur</h4>
                <ul className="lbc-analysis-list">
                  {result.questions_vendeur.map((question) => (
                    <li key={question}>{question}</li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}

        <p className="fin-meta">
          {comparables.count > 0
            ? `${comparables.count} annonces comparables collectées (« ${analysis.keywords} ») : médiane ${formatCents(
                comparables.median_cents,
              )}, de ${formatCents(comparables.min_cents)} à ${formatCents(comparables.max_cents)}`
            : `Aucune annonce comparable collectée${analysis.keywords ? ` pour « ${analysis.keywords} »` : ''}.`}
        </p>

        {analysis.sources.length > 0 && (
          <>
            <h4 className="lbc-analysis-title">Sources</h4>
            <ul className="lbc-analysis-list fin-meta">
              {analysis.sources.filter((s) => isHttpsUrl(s.url)).map((s) => (
                <li key={s.url}>
                  <a href={s.url} target="_blank" rel="noreferrer noopener">
                    {s.title}
                  </a>
                </li>
              ))}
            </ul>
          </>
        )}

        <details>
          <summary>Annonce et critères envoyés</summary>
          <p className="lbc-draft-body">{analysis.ad_text}</p>
          {analysis.criteria && <p className="lbc-draft-body fin-meta">Critères : {analysis.criteria}</p>}
        </details>
        <div className="fin-meta lbc-actions">
          <button type="button" className="link-button" onClick={remove}>
            supprimer
          </button>
        </div>
      </details>
    </li>
  )
}

export default function AnalysisSection({ onError }: { onError: (err: unknown) => void }) {
  const [analyses, setAnalyses] = useState<Analysis[] | null>(null)
  const [latest, setLatest] = useState<number | null>(null)

  const reload = useCallback(() => {
    api.get<Analysis[]>(`${BASE}/analyses`).then(setAnalyses).catch(onError)
  }, [onError])

  useEffect(reload, [reload])

  return (
    <div className="fin">
      <AnalysisForm
        onDone={(analysis) => {
          setLatest(analysis.id)
          reload()
        }}
      />
      {analyses === null ? (
        <p className="placeholder">Chargement…</p>
      ) : analyses.length === 0 ? (
        <p className="placeholder">Aucune annonce analysée pour l'instant.</p>
      ) : (
        <ul className="fin-list">
          {analyses.map((analysis) => (
            <AnalysisCard key={analysis.id} analysis={analysis} open={analysis.id === latest} onDelete={reload} />
          ))}
        </ul>
      )}
      <p className="disclaimer">
        Informations indicatives : vérifie toi-même avant d'acheter, et ne paie jamais hors de Leboncoin. Jarvis ne lit
        pas leboncoin.fr : colle le texte de l'annonce. Les e-mails, numéros de téléphone et IBAN sont retirés avant
        l'envoi à Claude, qui peut faire quelques recherches web (environ 1 centime chacune).
      </p>
    </div>
  )
}
