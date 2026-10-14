import { useEffect, useState } from 'react'
import { api, UnauthorizedError } from '../api'

const BASE = '/api/modules/veille_cyber'

interface Source {
  id: string
  label: string
  status: 'ok' | 'error' | null
}

interface Status {
  last_run: { started_at: string; finished_at: string | null; status: string; summary: string | null } | null
  last_success_at: string | null
  stale: boolean
  llm_enabled: boolean
  llm_cost_month_usd: number
  sources: Source[]
}

interface Article {
  id: number
  source: string
  link: string
  title: string
  summary: string
  published_at: string | null
  first_seen_at: string
}

interface Digest {
  day: string
  text: string | null
  articles: Article[]
}

const dateTime = (iso: string) =>
  new Date(iso).toLocaleString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

// Links come from external feeds: only https links are clickable.
const isHttps = (href: string) => {
  try {
    return new URL(href).protocol === 'https:'
  } catch {
    return false
  }
}

function StatusLine({ status }: { status: Status }) {
  const last = status.last_success_at
  return (
    <div className="vc-status">
      <span className={status.stale ? 'warning' : undefined}>
        {last ? `Dernière lecture : ${dateTime(last)}` : 'Aucune collecte réussie'}
      </span>
      {status.sources.map((source) => (
        <span key={source.id} className={source.status === 'error' ? 'warning' : undefined}>
          {source.label}
          {source.status === 'error' && ' : en panne'}
        </span>
      ))}
      <span>Claude : {status.llm_enabled ? `${status.llm_cost_month_usd.toFixed(4)} $ ce mois` : 'non configuré'}</span>
    </div>
  )
}

function ArticleItem({ article, labels }: { article: Article; labels: Record<string, string> }) {
  const when = article.published_at ?? article.first_seen_at
  return (
    <li className="vc-item">
      <div className="vc-item-head">
        {isHttps(article.link) ? (
          <a href={article.link} target="_blank" rel="noreferrer noopener">
            {article.title}
          </a>
        ) : (
          <span>{article.title}</span>
        )}
      </div>
      <div className="vc-item-product">
        <span className={article.source.startsWith('cert_fr') ? 'badge' : 'badge badge-press'}>
          {labels[article.source] ?? article.source}
        </span>{' '}
        {dateTime(when)}
      </div>
      {article.summary && <p className="vc-item-desc">{article.summary}</p>}
    </li>
  )
}

function History({ sources, labels }: { sources: Source[]; labels: Record<string, string> }) {
  const [source, setSource] = useState('')
  const [articles, setArticles] = useState<Article[] | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const query = source ? `&source=${encodeURIComponent(source)}` : ''
    api
      .get<Article[]>(`${BASE}/articles?days=7${query}`)
      .then(setArticles)
      .catch(() => setArticles([]))
  }, [open, source])

  return (
    <details className="vc-sheet" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>Historique des 7 derniers jours</summary>
      <label className="vc-filter">
        Source :{' '}
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">toutes</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </label>
      {articles === null ? (
        <p className="placeholder">Chargement…</p>
      ) : articles.length === 0 ? (
        <p className="placeholder">Aucun article.</p>
      ) : (
        <ul className="vc-list">
          {articles.map((a) => (
            <ArticleItem key={a.id} article={a} labels={labels} />
          ))}
        </ul>
      )}
    </details>
  )
}

export default function VeilleCyberWindow() {
  const [status, setStatus] = useState<Status | null>(null)
  const [digest, setDigest] = useState<Digest | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.get<Status>(`${BASE}/status`), api.get<Digest | null>(`${BASE}/digest/latest`)])
      .then(([s, d]) => {
        setStatus(s)
        setDigest(d)
      })
      .catch((err: unknown) =>
        setError(err instanceof UnauthorizedError ? 'Session expirée : recharge la page.' : 'Chargement impossible.'),
      )
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!status) return <p className="placeholder">Chargement…</p>

  const labels = Object.fromEntries(status.sources.map((s) => [s.id, s.label]))

  return (
    <div className="vc">
      <StatusLine status={status} />
      {!digest ? (
        <p className="placeholder">
          Pas encore d'actualités. Lance la collecte : <code>python -m app.collect veille_cyber</code>
        </p>
      ) : (
        <>
          <h3>Revue du {new Date(digest.day).toLocaleDateString('fr-FR')}</h3>
          {/* Plain text only: the summary is built from external feeds, never rendered as HTML. */}
          {digest.text && <div className="vc-digest">{digest.text}</div>}
          {digest.articles.length === 0 ? (
            <p className="placeholder">Rien de nouveau aujourd'hui.</p>
          ) : (
            <>
              {digest.text && <h3>Articles du jour</h3>}
              <ul className="vc-list">
                {digest.articles.map((a) => (
                  <ArticleItem key={a.id} article={a} labels={labels} />
                ))}
              </ul>
            </>
          )}
        </>
      )}
      <History sources={status.sources} labels={labels} />
      <p className="disclaimer">
        Sources : flux publics du CERT-FR (alertes, menaces, bulletins) et de Zataz. Les liens s'ouvrent sur le site
        d'origine.
      </p>
    </div>
  )
}
