// Web Worker: query embedding + cosine ranking for the semantic search page.
//
// All heavy lifting (loading transformers.js, downloading the ONNX model,
// running inference, scanning ~600 vectors) happens here so the main thread
// stays responsive.
//
// Message protocol (main → worker):
//   { type: 'init' }
//     Kicks off model + corpus loading. Worker reports progress with
//     'progress' messages and finishes with a 'ready' message.
//   { type: 'search', id, query, filters, topK }
//     Run a search. Worker replies with { type: 'results', id, ... }.
//
// Message protocol (worker → main):
//   { type: 'progress', stage, message, progress? }
//   { type: 'ready', total }
//   { type: 'results', id, durationMs, mergers }
//   { type: 'error', id?, message }

import { pipeline, env } from '@huggingface/transformers'

// Use the bundled onnxruntime-web wasm shipped inside @huggingface/transformers
// — Vite resolves `?url` imports to the final asset URL so this works in dev
// and production. Model weights themselves still come from the HF CDN.
env.allowLocalModels = false
env.allowRemoteModels = true

// Match the on-disk vectors. The corpus was encoded with EmbeddingGemma
// (Matryoshka-trained) and truncated to 256 dims. The query must use the same
// model and dim or cosine scores are meaningless.
const MODEL_ID = 'onnx-community/embeddinggemma-300m-ONNX'
const TARGET_DIM = 256
// EmbeddingGemma is asymmetric: documents and queries get different prompt
// prefixes. The embed pipeline used encode_document, which applies
// "title: none | text: <chunk>"; queries use the retrieval-query prompt below.
const QUERY_PROMPT = 'task: search result | query: '

let extractor = null
let corpus = null // { meta: [...], vectors: Float32Array, dim, count }
let initPromise = null

function post(msg) {
  self.postMessage(msg)
}

async function loadCorpus() {
  post({ type: 'progress', stage: 'corpus', message: 'Loading merger embeddings…' })
  const [metaResp, binResp] = await Promise.all([
    fetch('/data/embeddings.json'),
    fetch('/data/embeddings.bin'),
  ])
  if (!metaResp.ok) throw new Error(`embeddings.json: ${metaResp.status}`)
  if (!binResp.ok) throw new Error(`embeddings.bin: ${binResp.status}`)
  const meta = await metaResp.json()
  const buf = await binResp.arrayBuffer()
  const vectors = new Float32Array(buf)
  if (meta.length === 0) throw new Error('No embedding records')
  const dim = vectors.length / meta.length
  if (!Number.isInteger(dim)) {
    throw new Error(`Vector buffer (${vectors.length} floats) does not divide evenly into ${meta.length} records`)
  }
  return { meta, vectors, dim, count: meta.length }
}

async function loadModel() {
  post({ type: 'progress', stage: 'model', message: 'Loading embedding model…' })
  // Q4 quantisation keeps the download to ~80 MB (full FP32 is ~1.2 GB) and
  // runs inference in well under a second on commodity hardware.
  const ext = await pipeline('feature-extraction', MODEL_ID, {
    dtype: 'q4',
    progress_callback: (info) => {
      if (info.status === 'progress' && info.progress != null) {
        post({
          type: 'progress',
          stage: 'model',
          message: `Downloading model: ${info.file ?? ''}`,
          progress: info.progress,
        })
      }
    },
  })
  return ext
}

function ensureInit() {
  if (initPromise) return initPromise
  initPromise = (async () => {
    const [c, ext] = await Promise.all([loadCorpus(), loadModel()])
    corpus = c
    extractor = ext
    post({ type: 'ready', total: corpus.count })
  })().catch((err) => {
    initPromise = null
    post({ type: 'error', message: err.message || String(err) })
    throw err
  })
  return initPromise
}

async function embedQuery(text) {
  // Mean-pooled, L2-normalised embedding from the full 768-dim model.
  const output = await extractor(QUERY_PROMPT + text, {
    pooling: 'mean',
    normalize: true,
  })
  // Tensor → Float32Array. transformers.js puts the underlying typed array on
  // `.data`; toArray() also works but allocates a JS array.
  const full = output.data
  if (full.length < TARGET_DIM) {
    throw new Error(`Model returned ${full.length}-dim vector, need at least ${TARGET_DIM}`)
  }
  // Matryoshka truncation: take the first TARGET_DIM dims and renormalise so
  // cosine similarity against the (also-truncated) corpus vectors is correct.
  const truncated = new Float32Array(TARGET_DIM)
  let sumSq = 0
  for (let i = 0; i < TARGET_DIM; i++) {
    const v = full[i]
    truncated[i] = v
    sumSq += v * v
  }
  const norm = Math.sqrt(sumSq) || 1
  for (let i = 0; i < TARGET_DIM; i++) truncated[i] /= norm
  return truncated
}

function passesFilters(record, filters) {
  if (!filters) return true
  if (filters.outcome && filters.outcome !== 'all' && record.outcome !== filters.outcome) {
    return false
  }
  if (filters.year && filters.year !== 'all' && String(record.year) !== String(filters.year)) {
    return false
  }
  if (filters.industryCode && filters.industryCode !== 'all') {
    const codes = (record.industry || []).map((i) => String(i.code))
    if (!codes.includes(String(filters.industryCode))) return false
  }
  return true
}

function search(query, filters, topK) {
  const t0 = performance.now()
  const { meta, vectors, dim } = corpus
  const queryVec = query // already a Float32Array of length `dim`

  // Per-merger best chunk: scan all chunks once, take the highest-scoring one
  // for each merger_id. Pre-filtering on metadata is essentially free since
  // we already touch the record on the way past.
  const best = new Map() // merger_id → { score, idx, section }
  for (let i = 0; i < meta.length; i++) {
    const record = meta[i]
    if (!passesFilters(record, filters)) continue
    const offset = i * dim
    let dot = 0
    for (let j = 0; j < dim; j++) {
      dot += queryVec[j] * vectors[offset + j]
    }
    const prev = best.get(record.merger_id)
    if (!prev || dot > prev.score) {
      best.set(record.merger_id, { score: dot, idx: i, section: record.section })
    }
  }

  const ranked = Array.from(best.values()).sort((a, b) => b.score - a.score).slice(0, topK)

  const results = ranked.map((entry) => {
    const record = meta[entry.idx]
    return {
      mergerId: record.merger_id,
      mergerName: record.merger_name,
      parties: record.parties,
      industry: record.industry,
      outcome: record.outcome,
      date: record.date,
      year: record.year,
      score: entry.score,
      matchedSection: entry.section,
    }
  })

  return { results, durationMs: performance.now() - t0 }
}

self.addEventListener('message', async (event) => {
  const msg = event.data
  try {
    if (msg.type === 'init') {
      await ensureInit()
      return
    }
    if (msg.type === 'search') {
      await ensureInit()
      const queryVec = await embedQuery(msg.query)
      const { results, durationMs } = search(queryVec, msg.filters, msg.topK ?? 30)
      post({ type: 'results', id: msg.id, durationMs, mergers: results })
      return
    }
    post({ type: 'error', id: msg.id, message: `Unknown message type: ${msg.type}` })
  } catch (err) {
    post({ type: 'error', id: msg?.id, message: err.message || String(err) })
  }
})
