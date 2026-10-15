import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api } from '../../api'
import { formatCents } from '../finances/money'
import {
  BASE,
  CHECK_STATUSES,
  day,
  isHttpsUrl,
  URGENCIES,
  VERDICTS,
  type Analysis,
  type CheckStatus,
  type Vehicle,
} from './types'

const OPINION_MARKS = { positif: '+', negatif: '−', neutre: '·' } as const

const range = (minCents: number, maxCents: number) =>
  minCents === maxCents ? formatCents(minCents) : `${formatCents(minCents)} à ${formatCents(maxCents)}`

function AnalysisForm({ onDone }: { onDone: (analysis: Analysis) => void }) {
  const [text, setText] = useState('')
  const [keywords, setKeywords] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setRunning(true)
    setError(null)
    try {
      const analysis = await api.post<Analysis>(`${BASE}/analyses`, { text, keywords })
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

function Check({ label, check }: { label: string; check: { statut: CheckStatus; detail: string } }) {
  return (
    <li>
      <strong>{label}</strong> <span className={`badge lbc-status-${check.statut}`}>{CHECK_STATUSES[check.statut]}</span>
      {check.detail && <span className="fin-meta"> — {check.detail}</span>}
    </li>
  )
}

function VehiclePanel({ vehicle, total }: { vehicle: Vehicle; total: [number, number] | null }) {
  return (
    <div className="lbc-draft">
      <h4 className="lbc-analysis-title">Voiture</h4>
      <ul className="lbc-analysis-list lbc-plain-list">
        <Check label="Carte grise" check={vehicle.carte_grise} />
        <Check label="Contrôle technique" check={vehicle.controle_technique} />
      </ul>
      <h4 className="lbc-analysis-title">Réparations à prévoir</h4>
      {vehicle.reparations.length === 0 ? (
        <p className="fin-meta">Aucune repérée dans l'annonce.</p>
      ) : (
        <table className="lbc-repairs">
          <tbody>
            {vehicle.reparations.map((repair) => (
              <tr key={repair.element}>
                <td>{repair.element}</td>
                <td className={`lbc-urgency-${repair.urgence}`}>{URGENCIES[repair.urgence]}</td>
                <td className="fin-amount">{range(repair.cout_min_euros * 100, repair.cout_max_euros * 100)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {total && (
        <p className="lbc-total">
          Coût estimé : <strong>{range(total[0], total[1])}</strong>
          <span className="fin-meta">
            {' '}
            (prix
            {vehicle.frais_carte_grise_euros !== null &&
              ` + carte grise ${formatCents(vehicle.frais_carte_grise_euros * 100)}`}
            {vehicle.reparations.length > 0 && ' + réparations'})
          </span>
        </p>
      )}
    </div>
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
          {day(analysis.created_at)} ·{' '}
          {analysis.source === 'local'
            ? 'analyse locale (sans Claude)'
            : result
              ? 'analyse Claude'
              : 'analyse Claude dans un ancien format, relance-la'}
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
            {result.elements.length > 0 && (
              <>
                <h4 className="lbc-analysis-title">Ce que dit l'annonce</h4>
                <ul className="lbc-analysis-list lbc-plain-list">
                  {result.elements.map((element) => (
                    <li key={element.point} className={`lbc-opinion-${element.avis}`}>
                      <span aria-label={element.avis}>{OPINION_MARKS[element.avis]}</span> {element.point}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {result.vehicule && <VehiclePanel vehicle={result.vehicule} total={analysis.estimated_total_cents} />}
            <h4 className="lbc-analysis-title">Prix</h4>
            <p className="lbc-draft-body">{result.prix || 'Pas d’avis.'}</p>
            <h4 className="lbc-analysis-title">Fiabilité du modèle</h4>
            <p className="lbc-draft-body">{result.fiabilite || 'Rien trouvé.'}</p>
            <h4 className="lbc-analysis-title">Risque d'arnaque</h4>
            <p className="lbc-draft-body">{result.arnaque || 'Rien à signaler.'}</p>
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
              {analysis.sources
                .filter((s) => isHttpsUrl(s.url))
                .map((s) => (
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
          <summary>Annonce envoyée</summary>
          <p className="lbc-draft-body">{analysis.ad_text}</p>
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
        Informations indicatives : les coûts de réparation sont des estimations, fais inspecter la voiture et vérifie
        les documents (carte grise, contrôle technique, situation administrative sur HistoVec) avant d'acheter. Ne paie
        jamais hors de Leboncoin. Jarvis ne lit pas leboncoin.fr : colle le texte de l'annonce. Les e-mails, numéros de
        téléphone et IBAN sont retirés avant l'envoi à Claude, qui peut faire quelques recherches web (environ 1 centime
        chacune).
      </p>
    </div>
  )
}
