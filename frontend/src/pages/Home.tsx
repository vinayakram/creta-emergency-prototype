import React, { useMemo, useState } from 'react'

type SourceChunk = { id: string; page: number; chunk_id?: string; text: string; score: number }
type QueryResponse = {
  query: string
  steps: string[]
  warnings: string[]
  tools: string[]
  sources: SourceChunk[]
  disclaimer: string
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function Home() {
  const [query, setQuery] = useState('My battery is dead. How do I jump-start safely?')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<QueryResponse | null>(null)

  const canSubmit = useMemo(() => query.trim().length >= 3, [query])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const resp = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      })
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}))
        throw new Error(detail?.detail || `Request failed: ${resp.status}`)
      }
      const data = (await resp.json()) as QueryResponse
      setResult(data)
    } catch (err: any) {
      setError(err?.message || String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: '40px auto', padding: 16, fontFamily: 'system-ui, sans-serif' }}>
      <h1>Creta Emergency Assistant — Prototype v1</h1>
      <p style={{ opacity: 0.85 }}>
        Describe an emergency scenario. The system retrieves relevant manual excerpts and returns steps, warnings and tools.
      </p>

      <form onSubmit={onSubmit} style={{ display: 'flex', gap: 8 }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g., engine overheating, dead battery, flat tire..."
          style={{ flex: 1, padding: 12, fontSize: 16 }}
        />
        <button disabled={!canSubmit || loading} style={{ padding: '12px 16px', fontSize: 16 }}>
          {loading ? 'Searching…' : 'Get instructions'}
        </button>
      </form>

      {error && (
        <div style={{ marginTop: 16, padding: 12, border: '1px solid #f99' }}>
          <strong>Error:</strong> {error}
          <div style={{ marginTop: 8, opacity: 0.8 }}>
            First run? Make sure you indexed the PDF by running <code>02_INGEST_MANUAL.bat</code> and that the backend is running.
          </div>
        </div>
      )}

      {result && (
        <div style={{ marginTop: 24 }}>
          <div style={{ padding: 12, border: '1px solid #ddd' }}>
            <div style={{ fontSize: 14, opacity: 0.8 }}>Query</div>
            <div style={{ fontSize: 18 }}>{result.query}</div>
            <div style={{ marginTop: 10, fontSize: 13, opacity: 0.75 }}>{result.disclaimer}</div>
          </div>

          <section style={{ marginTop: 16 }}>
            <h2>Steps</h2>
            <ol>
              {result.steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          </section>

          <section style={{ marginTop: 16 }}>
            <h2>Warnings / Cautions</h2>
            {result.warnings.length === 0 ? (
              <p style={{ opacity: 0.8 }}>No explicit WARNING/CAUTION lines found in retrieved excerpts.</p>
            ) : (
              <ul>
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </section>

          <section style={{ marginTop: 16 }}>
            <h2>Required tools (simple detection)</h2>
            {result.tools.length === 0 ? (
              <p style={{ opacity: 0.8 }}>None detected.</p>
            ) : (
              <ul>
                {result.tools.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            )}
          </section>

          <section style={{ marginTop: 16 }}>
            <h2>Sources</h2>
            <p style={{ opacity: 0.8 }}>Top retrieved manual excerpts (with page numbers).</p>
            {result.sources.map((c) => (
              <details key={c.id} style={{ marginBottom: 10, border: '1px solid #eee', padding: 10 }}>
                <summary>
                  Page {c.page} • {c.chunk_id || c.id} • score {c.score.toFixed(4)}
                </summary>
                <pre style={{ whiteSpace: 'pre-wrap' }}>{c.text}</pre>
              </details>
            ))}
          </section>
        </div>
      )}
    </div>
  )
}
