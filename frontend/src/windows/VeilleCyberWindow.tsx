import { useEffect, useState } from 'react'
import { api, UnauthorizedError } from '../api'

const BASE = '/api/modules/veille_cyber'
const STALE_AFTER_HOURS = 36

interface Status {
  last_run: { started_at: string; status: string; summary: string | null } | null
  last_success_at: string | null
  llm_enabled: boolean
  skills_file_found: boolean
  llm_cost_month_usd: number
}

interface Vulnerability {
  cve_id: string
  vendor: string | null
  product: string | null
  title: string | null
  description: string
  cvss_score: number | null
  cvss_severity: string | null
  cvss_version: string | null
  epss: number | null
  in_kev: boolean
  kev_due_date: string | null
  ransomware: boolean
}

interface Digest {
  day: string
  text: string | null
  vulnerabilities: Vulnerability[]
}

interface Sheet {
  vendor: string | null
  product: string
  text: string
}

const dateTime = (iso: string) =>
  new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })

function StatusLine({ status }: { status: Status }) {
  const last = status.last_success_at
  const stale = !last || Date.now() - new Date(last).getTime() > STALE_AFTER_HOURS * 3600_000
  return (
    <div className="vc-status">
      <span className={stale ? 'warning' : undefined}>
        {last ? `Dernière collecte : ${dateTime(last)}` : 'Aucune collecte réussie'}
        {stale && last && ' (ancienne)'}
      </span>
      {status.last_run?.status === 'error' && <span className="warning">Échec de la dernière collecte</span>}
      <span>
        Claude : {status.llm_enabled ? `${status.llm_cost_month_usd.toFixed(4)} $ ce mois` : 'non configuré'}
      </span>
      {status.llm_enabled && !status.skills_file_found && <span className="warning">skills.md introuvable</span>}
    </div>
  )
}

function VulnerabilityItem({ vuln }: { vuln: Vulnerability }) {
  return (
    <li className="vc-item">
      <div className="vc-item-head">
        <a href={`https://nvd.nist.gov/vuln/detail/${vuln.cve_id}`} target="_blank" rel="noreferrer noopener">
          {vuln.cve_id}
        </a>
        {vuln.in_kev && <span className="badge badge-danger">Exploitée (KEV)</span>}
        {vuln.ransomware && <span className="badge badge-danger">Rançongiciel</span>}
        {vuln.cvss_score !== null && (
          <span className="badge">
            CVSS {vuln.cvss_version} {vuln.cvss_score}
          </span>
        )}
        {vuln.epss !== null && <span className="badge">EPSS {(vuln.epss * 100).toFixed(1)} %</span>}
      </div>
      <div className="vc-item-product">
        {[vuln.vendor, vuln.product].filter(Boolean).join(' ') || 'Produit non identifié'}
        {vuln.kev_due_date && ` · échéance CISA ${vuln.kev_due_date}`}
      </div>
      <p className="vc-item-desc">{vuln.title || vuln.description}</p>
    </li>
  )
}

export default function VeilleCyberWindow() {
  const [status, setStatus] = useState<Status | null>(null)
  const [digest, setDigest] = useState<Digest | null>(null)
  const [sheets, setSheets] = useState<Sheet[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      api.get<Status>(`${BASE}/status`),
      api.get<Digest | null>(`${BASE}/digest/latest`),
      api.get<Sheet[]>(`${BASE}/sheets`),
    ])
      .then(([s, d, sh]) => {
        setStatus(s)
        setDigest(d)
        setSheets(sh)
      })
      .catch((err: unknown) =>
        setError(err instanceof UnauthorizedError ? 'Session expirée : recharge la page.' : 'Chargement impossible.'),
      )
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!status) return <p className="placeholder">Chargement…</p>

  return (
    <div className="vc">
      <StatusLine status={status} />
      {!digest ? (
        <p className="placeholder">
          Pas encore de données. Lance la collecte : <code>python -m app.collect veille_cyber</code>
        </p>
      ) : (
        <>
          <h3>Veille du {new Date(digest.day).toLocaleDateString('fr-FR')}</h3>
          {/* Plain text only: the summary is built from external data, never rendered as HTML. */}
          {digest.text && <div className="vc-digest">{digest.text}</div>}
          {digest.vulnerabilities.length === 0 ? (
            <p className="placeholder">Rien de nouveau aujourd'hui.</p>
          ) : (
            <ul className="vc-list">
              {digest.vulnerabilities.map((v) => (
                <VulnerabilityItem key={v.cve_id} vuln={v} />
              ))}
            </ul>
          )}
        </>
      )}
      {sheets.length > 0 && (
        <>
          <h3>Fiches logiciels</h3>
          {sheets.map((sheet) => (
            <details key={`${sheet.vendor}-${sheet.product}`} className="vc-sheet">
              <summary>{[sheet.vendor, sheet.product].filter(Boolean).join(' ')}</summary>
              <div className="vc-digest">{sheet.text}</div>
            </details>
          ))}
        </>
      )}
      <p className="disclaimer">Sources : CISA KEV, NIST NVD, FIRST EPSS.</p>
    </div>
  )
}
