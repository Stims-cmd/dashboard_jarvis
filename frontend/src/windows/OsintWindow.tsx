import { useEffect, useState } from 'react'
import { api, UnauthorizedError } from '../api'

const BASE = '/api/modules/osint'

interface Finding {
  id: number
  kind: 'breach' | 'mention' | 'account' | 'gravatar'
  subject: string
  source: string
  key: string
  title: string
  details: Record<string, unknown>
  first_seen_at: string
  last_seen_at: string
}

interface Report {
  week: string
  created_at: string
  sources: Record<string, string>
  new_findings: Finding[]
}

interface Status {
  last_success_at: string | null
  last_run_status: string | null
  stale: boolean
  targets_file_found: boolean
  brave_enabled: boolean
  total_findings: number
}

const KIND_TITLES: Record<Finding['kind'], string> = {
  breach: 'Fuites de données',
  mention: 'Mentions sur le web',
  account: 'Comptes trouvés',
  gravatar: 'Profils publics',
}
const SOURCE_STATUS: Record<string, string> = { ok: 'OK', error: 'erreur', disabled: 'désactivée' }

const day = (iso: string) => new Date(iso).toLocaleDateString('fr-FR')
const text = (value: unknown) => (typeof value === 'string' ? value : '')

// Only http(s) links are rendered as links: external data is never trusted as-is.
function SafeLink({ href, children }: { href: string; children: string }) {
  if (!/^https?:\/\//.test(href)) return <span>{children}</span>
  return (
    <a href={href} target="_blank" rel="noreferrer noopener">
      {children}
    </a>
  )
}

function FindingItem({ finding }: { finding: Finding }) {
  const d = finding.details
  switch (finding.kind) {
    case 'breach':
      return (
        <li className="vc-item">
          <div className="vc-item-head">
            {finding.title}
            {text(d.year) && <span className="badge">{text(d.year)}</span>}
            {d.password_risk === 'plaintext' && <span className="badge badge-danger">mots de passe en clair</span>}
          </div>
          <div className="vc-item-product">
            {finding.subject} · données exposées : {Array.isArray(d.data) ? d.data.join(', ') : '?'}
          </div>
          <p className="vc-item-desc">
            Si tu as un compte sur ce service : change son mot de passe (et partout où tu l'as réutilisé) et
            active la double authentification.
          </p>
        </li>
      )
    case 'mention':
      return (
        <li className="vc-item">
          <div className="vc-item-head">
            <SafeLink href={finding.key}>{finding.title}</SafeLink>
          </div>
          <div className="vc-item-product">{finding.subject}</div>
          {text(d.snippet) && <p className="vc-item-desc">{text(d.snippet)}</p>}
        </li>
      )
    default:
      return (
        <li className="vc-item">
          <div className="vc-item-head">
            <SafeLink href={text(d.url)}>{finding.title}</SafeLink>
          </div>
          <div className="vc-item-product">
            {finding.subject} · vu pour la première fois le {day(finding.first_seen_at)}
          </div>
        </li>
      )
  }
}

function Grouped({ findings }: { findings: Finding[] }) {
  return (
    <>
      {(Object.keys(KIND_TITLES) as Finding['kind'][]).map((kind) => {
        const items = findings.filter((f) => f.kind === kind)
        if (items.length === 0) return null
        return (
          <section key={kind}>
            <h3>
              {KIND_TITLES[kind]} ({items.length})
            </h3>
            <ul className="vc-list">
              {items.map((f) => (
                <FindingItem key={f.id} finding={f} />
              ))}
            </ul>
          </section>
        )
      })}
    </>
  )
}

export default function OsintWindow() {
  const [status, setStatus] = useState<Status | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [history, setHistory] = useState<Finding[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.get<Status>(`${BASE}/status`), api.get<Report | null>(`${BASE}/report/latest`)])
      .then(([s, r]) => {
        setStatus(s)
        setReport(r)
      })
      .catch((err: unknown) =>
        setError(err instanceof UnauthorizedError ? 'Session expirée : recharge la page.' : 'Chargement impossible.'),
      )
  }, [])

  function loadHistory() {
    if (history === null) api.get<Finding[]>(`${BASE}/findings`).then(setHistory).catch(() => setHistory([]))
  }

  if (error) return <p className="error">{error}</p>
  if (!status) return <p className="placeholder">Chargement…</p>

  return (
    <div className="vc">
      <div className="vc-status">
        <span className={status.stale ? 'warning' : undefined}>
          {status.last_success_at ? `Dernier rapport : ${day(status.last_success_at)}` : 'Aucune collecte réussie'}
        </span>
        {!status.targets_file_found && <span className="warning">data/osint.toml introuvable</span>}
        {report &&
          Object.entries(report.sources).map(([source, state]) => (
            <span key={source} className={state === 'error' ? 'warning' : undefined}>
              {source} : {SOURCE_STATUS[state] ?? state}
            </span>
          ))}
      </div>

      {!report ? (
        <p className="placeholder">
          Pas encore de rapport. Remplis <code>data/osint.toml</code> puis lance{' '}
          <code>python -m app.collect osint</code>.
        </p>
      ) : (
        <>
          <h3>Nouveautés de la semaine du {day(report.week)}</h3>
          {report.new_findings.length === 0 ? (
            <p className="placeholder">Rien de nouveau cette semaine.</p>
          ) : (
            <Grouped findings={report.new_findings} />
          )}
        </>
      )}

      {status.total_findings > 0 && (
        <details className="vc-sheet" onToggle={loadHistory}>
          <summary>Historique complet ({status.total_findings})</summary>
          {history === null ? <p className="placeholder">Chargement…</p> : <Grouped findings={history} />}
        </details>
      )}
      <p className="disclaimer">
        Surveillance de tes propres identifiants uniquement. Sources : XposedOrNot, Brave Search, API publiques
        des plateformes, Gravatar.
      </p>
    </div>
  )
}
