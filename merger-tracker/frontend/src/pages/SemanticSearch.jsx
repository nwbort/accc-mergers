import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import SEO from '../components/SEO'
import StatusBadge from '../components/StatusBadge'
import { formatDate } from '../utils/dates'
import { API_ENDPOINTS } from '../config'

// Hidden test page for the in-browser semantic search prototype. Not linked
// from the navbar — reach it via /search.
//
// Architecture (see also src/workers/semanticSearch.worker.js):
//   - Web Worker owns the embedding model and the corpus vectors.
//   - Main thread handles UI state, filters, and lazy-fetched snippets.
//   - Snippets aren't shipped with the embeddings; we re-derive them on
//     demand from the existing /data/mergers/{id}.json files.

const SECTION_LABELS = {
  overview: 'Overview',
  parties: 'Parties',
  overlap: 'Overlap',
  reasons: 'Reasons',
  industry_background: 'Industry background',
}

// Maps the canonical section keys back to the determination-table item names
// the backend actually stores. Mirrors scripts/embed.py's ITEM_TO_SECTION
// table — kept here because the chunk text isn't shipped with the embeddings
// and the snippet needs to be reconstructed from the merger JSON.
const SECTION_ITEM_PATTERNS = {
  overview: ['notified acquisition', 'acquisition'],
  parties: ['parties to the acquisition'],
  overlap: [
    'overlap and relationship between the parties',
    'overlap between the parties',
    'relationship between the parties',
  ],
  reasons: ['explanation for determination', 'reasons for determination'],
  industry_background: ['industry background'],
}

function snippetForSection(merger, sectionKey) {
  if (!merger || !sectionKey) return null
  // Overview falls back to the human-written merger description (matches
  // embed.py, which prepends merger_description to the overview chunk).
  if (sectionKey === 'overview' && merger.merger_description) {
    const det = findDeterminationRows(merger, SECTION_ITEM_PATTERNS.overview)
    const parts = [merger.merger_description, ...det]
    return cleanupSnippet(parts.join('\n\n'))
  }
  const patterns = SECTION_ITEM_PATTERNS[sectionKey]
  if (!patterns) return null
  const rows = findDeterminationRows(merger, patterns)
  return rows.length ? cleanupSnippet(rows.join('\n\n')) : null
}

function findDeterminationRows(merger, patterns) {
  const events = merger.events || []
  const collected = []
  for (const event of events) {
    const rows = event.determination_table_content || []
    for (const row of rows) {
      const item = (row.item || '').replace(/\s+/g, ' ').trim().toLowerCase()
      if (patterns.some((p) => item.startsWith(p))) {
        const details = (row.details || '').trim()
        if (details) collected.push(details)
      }
    }
  }
  return collected
}

function cleanupSnippet(text) {
  if (!text) return ''
  return text.replace(/\xa0/g, ' ').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim()
}

const MAX_SNIPPET_CHARS = 600

function truncate(text, max = MAX_SNIPPET_CHARS) {
  if (!text || text.length <= max) return text
  // Snip at a word boundary so we don't cut mid-word.
  const slice = text.slice(0, max)
  const lastSpace = slice.lastIndexOf(' ')
  return slice.slice(0, lastSpace > max - 80 ? lastSpace : max).trimEnd() + '…'
}

function SemanticSearch() {
  const workerRef = useRef(null)
  const requestIdRef = useRef(0)
  const pendingSearchRef = useRef(null)
  const lastQueryRef = useRef('')
  const snippetCacheRef = useRef(new Map())

  const [workerStatus, setWorkerStatus] = useState('idle') // idle | loading | ready | error
  const [progressMessage, setProgressMessage] = useState('')
  const [progressFraction, setProgressFraction] = useState(null)
  const [errorMessage, setErrorMessage] = useState(null)

  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchInfo, setSearchInfo] = useState(null) // { query, durationMs, count }
  const [results, setResults] = useState([])

  const [outcomeFilter, setOutcomeFilter] = useState('all')
  const [yearFilter, setYearFilter] = useState('all')
  const [industryFilter, setIndustryFilter] = useState('all')
  const [filterOptions, setFilterOptions] = useState({ outcomes: [], years: [], industries: [] })

  // Pre-fetch the embedding metadata once on mount so the filter dropdowns
  // can show real options before the user kicks off a search. The worker
  // also fetches this file, but Cache-Control + the 200 KB size make the
  // duplicate request cheap.
  useEffect(() => {
    let cancelled = false
    fetch('/data/embeddings.json')
      .then((r) => (r.ok ? r.json() : []))
      .then((records) => {
        if (cancelled) return
        const outcomes = new Set()
        const years = new Set()
        const industries = new Map()
        for (const r of records) {
          if (r.outcome) outcomes.add(r.outcome)
          if (r.year) years.add(r.year)
          for (const ind of r.industry || []) {
            if (ind?.code) industries.set(String(ind.code), ind.name || String(ind.code))
          }
        }
        setFilterOptions({
          outcomes: Array.from(outcomes).sort(),
          years: Array.from(years).sort((a, b) => b - a),
          industries: Array.from(industries.entries()).sort((a, b) => a[1].localeCompare(b[1])),
        })
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const ensureWorker = useCallback(() => {
    if (workerRef.current) return workerRef.current
    setWorkerStatus('loading')
    setProgressMessage('Starting search engine…')
    const worker = new Worker(
      new URL('../workers/semanticSearch.worker.js', import.meta.url),
      { type: 'module' }
    )
    worker.addEventListener('message', (event) => {
      const msg = event.data
      if (msg.type === 'progress') {
        setProgressMessage(msg.message || '')
        setProgressFraction(typeof msg.progress === 'number' ? msg.progress : null)
      } else if (msg.type === 'ready') {
        setWorkerStatus('ready')
        setProgressMessage('')
        setProgressFraction(null)
        // If the user typed and submitted while the model was still loading,
        // run that pending query now instead of dropping it.
        if (pendingSearchRef.current) {
          const p = pendingSearchRef.current
          pendingSearchRef.current = null
          runSearchOnWorker(p.query, p.filters)
        }
      } else if (msg.type === 'results') {
        setSearching(false)
        setSearchInfo({
          query: lastQueryRef.current,
          durationMs: msg.durationMs,
          count: msg.mergers.length,
        })
        setResults(msg.mergers.map((m) => ({ ...m, snippetState: 'idle', snippet: null })))
      } else if (msg.type === 'error') {
        setSearching(false)
        setWorkerStatus((s) => (s === 'loading' ? 'error' : s))
        setErrorMessage(msg.message || 'Unknown error')
      }
    })
    worker.addEventListener('error', (event) => {
      setWorkerStatus('error')
      setErrorMessage(event.message || 'Worker crashed')
    })
    workerRef.current = worker
    worker.postMessage({ type: 'init' })
    return worker
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    return () => {
      workerRef.current?.terminate()
      workerRef.current = null
    }
  }, [])

  const runSearchOnWorker = useCallback((q, filters) => {
    const worker = workerRef.current
    if (!worker) return
    const id = ++requestIdRef.current
    lastQueryRef.current = q
    setSearching(true)
    setErrorMessage(null)
    worker.postMessage({ type: 'search', id, query: q, filters, topK: 30 })
  }, [])

  const onSubmit = useCallback(
    (event) => {
      event.preventDefault()
      const trimmed = query.trim()
      if (!trimmed) return
      const filters = {
        outcome: outcomeFilter,
        year: yearFilter,
        industryCode: industryFilter,
      }
      ensureWorker()
      if (workerStatus !== 'ready') {
        // Queue the search; we'll dispatch it once the worker is ready.
        pendingSearchRef.current = { query: trimmed, filters }
        return
      }
      runSearchOnWorker(trimmed, filters)
    },
    [query, outcomeFilter, yearFilter, industryFilter, workerStatus, ensureWorker, runSearchOnWorker]
  )

  // Snippet-on-demand: lazy-fetch the merger JSON for an expanded card and
  // pull just the chunk that produced the match. Cached so re-expanding is
  // instant.
  const loadSnippet = useCallback(async (idx) => {
    setResults((current) => {
      if (!current[idx] || current[idx].snippetState !== 'idle') return current
      const next = current.slice()
      next[idx] = { ...next[idx], snippetState: 'loading' }
      return next
    })
    const target = results[idx]
    if (!target) return
    const cacheKey = `${target.mergerId}:${target.matchedSection}`
    let snippet = snippetCacheRef.current.get(cacheKey)
    if (snippet === undefined) {
      try {
        const resp = await fetch(API_ENDPOINTS.mergerDetail(target.mergerId))
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
        const merger = await resp.json()
        snippet = snippetForSection(merger, target.matchedSection) || ''
        snippetCacheRef.current.set(cacheKey, snippet)
      } catch (err) {
        snippet = ''
        snippetCacheRef.current.set(cacheKey, snippet)
        console.warn('Failed to load snippet', err)
      }
    }
    setResults((current) => {
      const next = current.slice()
      const row = next[idx]
      if (!row) return current
      next[idx] = { ...row, snippetState: 'loaded', snippet }
      return next
    })
  }, [results])

  const partiesSummary = useCallback((parties) => {
    if (!parties || parties.length === 0) return ''
    if (parties.length <= 2) return parties.join(' / ')
    return `${parties[0]} / ${parties[1]} (+${parties.length - 2} more)`
  }, [])

  const exampleQueries = useMemo(
    () => [
      'vertical effects in supply chains',
      'fuel retailing concentration',
      'private equity acquisition of healthcare provider',
      'data centre infrastructure',
      'phase 2 review reasons',
    ],
    []
  )

  return (
    <>
      <SEO
        title="Semantic search (preview)"
        description="Prototype semantic search over ACCC merger determinations."
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Semantic search</h1>
          <p className="mt-2 text-sm text-gray-600 max-w-2xl">
            Preview of in-browser semantic search over ACCC merger determinations. The
            embedding model (~80 MB) downloads once on first use and is cached by your
            browser; everything runs locally — no server. Try the example queries below
            or describe what you're looking for in your own words.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {exampleQueries.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => setQuery(q)}
                className="text-xs px-3 py-1 rounded-full border border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={onSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
          <label htmlFor="semantic-search-input" className="sr-only">Search query</label>
          <div className="flex gap-2">
            <input
              id="semantic-search-input"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Describe a deal, theory of harm, market, etc."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              autoFocus
            />
            <button
              type="submit"
              disabled={!query.trim() || searching}
              className="px-4 py-2 bg-primary text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
            >
              {searching ? 'Searching…' : 'Search'}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
            <select
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
              aria-label="Filter by outcome"
            >
              <option value="all">All outcomes</option>
              {filterOptions.outcomes.map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
            <select
              value={yearFilter}
              onChange={(e) => setYearFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
              aria-label="Filter by year"
            >
              <option value="all">All years</option>
              {filterOptions.years.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <select
              value={industryFilter}
              onChange={(e) => setIndustryFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
              aria-label="Filter by industry"
            >
              <option value="all">All industries</option>
              {filterOptions.industries.map(([code, name]) => (
                <option key={code} value={code}>{name}</option>
              ))}
            </select>
          </div>
        </form>

        {workerStatus === 'loading' && (
          <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-4 mb-6 text-sm">
            <div className="font-medium">{progressMessage || 'Loading…'}</div>
            {progressFraction != null && (
              <div className="mt-2 h-2 bg-blue-100 rounded overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all"
                  style={{ width: `${Math.min(100, Math.round(progressFraction))}%` }}
                />
              </div>
            )}
            <div className="text-xs text-blue-700 mt-2">
              First load only — the model is cached by your browser after this.
            </div>
          </div>
        )}

        {errorMessage && (
          <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-4 mb-6 text-sm">
            <div className="font-medium">Search engine error</div>
            <div className="mt-1">{errorMessage}</div>
          </div>
        )}

        {searchInfo && !searching && (
          <div className="text-xs text-gray-500 mb-3">
            {searchInfo.count} result{searchInfo.count === 1 ? '' : 's'} in{' '}
            {Math.round(searchInfo.durationMs)} ms
          </div>
        )}

        <div className="space-y-3">
          {results.map((r, idx) => (
            <article
              key={`${r.mergerId}-${idx}`}
              className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <Link
                    to={`/mergers/${r.mergerId}`}
                    className="text-base font-semibold text-gray-900 hover:text-primary truncate block"
                  >
                    {r.mergerName || r.mergerId}
                  </Link>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {r.mergerId}
                    {r.date && <> · {formatDate(r.date)}</>}
                  </div>
                  {r.parties?.length > 0 && (
                    <div className="text-sm text-gray-600 mt-1 truncate">
                      {partiesSummary(r.parties)}
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                  <span className="text-xs font-mono text-gray-500">
                    {r.score.toFixed(3)}
                  </span>
                  <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded bg-gray-100 text-gray-700 border border-gray-200">
                    Matched: {SECTION_LABELS[r.matchedSection] || r.matchedSection}
                  </span>
                  {r.outcome && (
                    <StatusBadge determination={r.outcome} status={r.outcome} />
                  )}
                </div>
              </div>

              {r.industry?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {r.industry.slice(0, 4).map((ind) => (
                    <span
                      key={ind.code}
                      className="text-[10px] px-2 py-0.5 rounded bg-gray-50 text-gray-600 border border-gray-200"
                    >
                      {ind.name}
                    </span>
                  ))}
                </div>
              )}

              <div className="mt-3">
                {r.snippetState === 'idle' && (
                  <button
                    type="button"
                    onClick={() => loadSnippet(idx)}
                    className="text-xs text-primary hover:underline"
                  >
                    Show matched section →
                  </button>
                )}
                {r.snippetState === 'loading' && (
                  <div className="text-xs text-gray-400">Loading section…</div>
                )}
                {r.snippetState === 'loaded' && (
                  r.snippet ? (
                    <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                      {truncate(r.snippet)}
                    </p>
                  ) : (
                    <div className="text-xs text-gray-400">No snippet available.</div>
                  )
                )}
              </div>
            </article>
          ))}
          {!searching && results.length === 0 && searchInfo && (
            <div className="text-center text-gray-500 py-8 text-sm">
              No results matched the current filters.
            </div>
          )}
        </div>
      </div>
    </>
  )
}

export default SemanticSearch
