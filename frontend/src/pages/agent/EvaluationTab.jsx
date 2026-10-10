import { useState, useEffect, useRef } from 'react'

export default function EvaluationTab({ id, api, active }) {
  const [snapshots, setSnapshots] = useState([])
  const [newSnapshotName, setNewSnapshotName] = useState('')
  const [evalSnapshotId, setEvalSnapshotId] = useState('')
  const [evalLanguage, setEvalLanguage] = useState('en')
  const [evalNExec, setEvalNExec] = useState(3)
  const [runningEval, setRunningEval] = useState(false)
  const [evalMsg, setEvalMsg] = useState('')
  const [evalRuns, setEvalRuns] = useState([])
  const [expandedRunId, setExpandedRunId] = useState('')
  const [expandedRunDetail, setExpandedRunDetail] = useState(null)
  const [chartHoveredIdx, setChartHoveredIdx] = useState(null)
  const evalFileRef = useRef()

  const fetchSnapshots = async () => {
    const res = await api.get(`/api/agents/${id}/config-snapshots`)
    if (res.ok) setSnapshots(await res.json())
  }

  const handleCreateSnapshot = async () => {
    await api.post(`/api/agents/${id}/config-snapshots`, { name: newSnapshotName.trim() || undefined })
    setNewSnapshotName('')
    await fetchSnapshots()
  }

  const handleDeleteSnapshot = async (snapshotId) => {
    if (!globalThis.confirm('Delete this saved configuration? This cannot be undone.')) return
    await api.delete(`/api/agents/${id}/config-snapshots/${snapshotId}`)
    await fetchSnapshots()
  }

  const fetchEvalRuns = async () => {
    const res = await api.get(`/api/agents/${id}/evaluations`)
    if (res.ok) setEvalRuns(await res.json())
  }

  const handleRunEvaluation = async (e) => {
    e.preventDefault()
    const file = evalFileRef.current.files[0]
    if (!file || !evalSnapshotId) return

    setRunningEval(true)
    setEvalMsg('')
    const form = new FormData()
    form.append('file', file)
    form.append('snapshot_id', evalSnapshotId)
    form.append('language', evalLanguage)
    form.append('n_exec', evalNExec)


    const res = await api.upload(`/api/agents/${id}/evaluations`, form)
    const data = await res.json()
    setRunningEval(false)
    setEvalMsg(res.ok ? 'Evaluation started — it will appear below once finished.' : (data.error || 'Error starting evaluation'))
    if (res.ok) {
      evalFileRef.current.value = ''
      await fetchEvalRuns()
    }
  }

  const handleToggleRunDetail = async (runId) => {
    if (expandedRunId === runId) {
      setExpandedRunId('')
      setExpandedRunDetail(null)
      return
    }
    setExpandedRunId(runId)
    const res = await api.get(`/api/agents/${id}/evaluations/${runId}`)
    if (res.ok) setExpandedRunDetail(await res.json())
  }

  const handleDownloadCSV = async (r) => {
    let detail = (expandedRunId === r._id && expandedRunDetail) ? expandedRunDetail : null
    if (!detail) {
      const res = await api.get(`/api/agents/${id}/evaluations/${r._id}`)
      if (!res.ok) return
      detail = await res.json()
    }
    const perQ = detail.results?.per_question ?? []
    const rows = [
      'Question;answer;Binary;Quality;BERT',
      ...perQ.map(pq => [
        `"${(pq.question  ?? '').replace(/"/g, '""')}"`,
        `"${(pq.last_answer ?? '').replace(/"/g, '""')}"`,
        pq.score?.mean ?? '',
        pq.rouge1_mean  ?? '',
        pq.bertscore_mean ?? '',
      ].join(';'))
    ].join('\n')
    const blob = new Blob([rows], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `eval_${r.snapshot_name.replace(/\s+/g,'_')}_${r._id.slice(-6)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDeleteRun = async (runId) => {
    if (!globalThis.confirm('Delete this evaluation run? This cannot be undone.')) return
    await api.delete(`/api/agents/${id}/evaluations/${runId}`)
    if (expandedRunId === runId) { setExpandedRunId(''); setExpandedRunDetail(null) }
    await fetchEvalRuns()
  }

  useEffect(() => {
    if (active) { fetchSnapshots(); fetchEvalRuns() }
  }, [active])

  // Auto-refresh mientras haya alguna evaluación en curso (rápido, para mostrar avance paso a paso)
  useEffect(() => {
    const hasRunning = evalRuns.some(r => r.status === 'running')
    if (!hasRunning) return
    const interval = setInterval(fetchEvalRuns, 3000)
    return () => clearInterval(interval)
  }, [evalRuns])

  return (
    <div className="space-y-8">

      {/* Configuraciones guardadas */}
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Saved configurations</p>
        <div className="flex gap-2 mb-4">
          <input
            value={newSnapshotName}
            onChange={e => setNewSnapshotName(e.target.value)}
            placeholder="Configuration name (optional)"
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
          />
          <button
            onClick={handleCreateSnapshot}
            className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition"
          >
            + Save current configuration
          </button>
        </div>
        {snapshots.length === 0 ? (
          <p className="text-sm text-gray-300">No saved configurations yet.</p>
        ) : (
          <div className="space-y-2">
            {snapshots.map(s => (
              <div key={s._id} className="flex items-center justify-between border border-gray-100 rounded-lg px-4 py-3">
                <div>
                  <p className="text-sm text-gray-700">{s.name}</p>
                  {s.rag_config && (() => {
                    const cfg = s.rag_config
                    const tags = [
                      cfg.retrieval_mode && `retrieval: ${cfg.retrieval_mode}`,
                      cfg.synthesis_mode && `synthesis: ${cfg.synthesis_mode}`,
                      cfg.similarity_top_k != null && `top_k: ${cfg.similarity_top_k}`,
                      cfg.chunk_size != null && `chunk: ${cfg.chunk_size}/${cfg.chunk_overlap ?? 0}`,
                      cfg.temperature != null && `temp: ${cfg.temperature}`,
                      cfg.rerank && `rerank`,
                      cfg.sim_filter && `sim_filter: ${cfg.similarity_cutoff ?? ''}`,
                      s.llm_model && `model: ${s.llm_model}`,
                    ].filter(Boolean)
                    return (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {tags.map(t => (
                          <span key={t} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{t}</span>
                        ))}
                      </div>
                    )
                  })()}
                </div>
                <button
                  onClick={() => handleDeleteSnapshot(s._id)}
                  className="text-xs text-red-400 hover:text-red-500 transition"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Lanzar evaluación */}
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Run evaluation</p>
        <form onSubmit={handleRunEvaluation} className="space-y-3 border border-gray-100 rounded-xl px-5 py-4">

          <div>
            <label htmlFor="eval-snapshot-select" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Configuration to test</label>
            <select
              id="eval-snapshot-select"
              value={evalSnapshotId}
              onChange={e => setEvalSnapshotId(e.target.value)}
              required
              className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 bg-white"
            >
              <option value="">— Select a saved configuration —</option>
              {snapshots.map(s => (
                <option key={s._id} value={s._id}>{s.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="eval-csv-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Questions dataset (.csv)</label>
            <input
              id="eval-csv-input"
              type="file"
              accept=".csv"
              ref={evalFileRef}
              required
              className="w-full text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">
              Columns separated by semicolons: Question;Keywords;Answer (Answer is optional).
            </p>
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label htmlFor="eval-language-select" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Language</label>
              <select
                id="eval-language-select"
                value={evalLanguage}
                onChange={e => setEvalLanguage(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 bg-white"
              >
                <option value="en">English</option>
                <option value="es">Español</option>
              </select>
            </div>
            <div className="flex-1">
              <label htmlFor="eval-nexec-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Repetitions per question</label>
              <input
                id="eval-nexec-input"
                type="number"
                min="1"
                max="10"
                value={evalNExec}
                onChange={e => setEvalNExec(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </div>
          </div>


          <div className="flex items-center justify-end gap-3 pt-2">
            {evalMsg && <span className="text-sm text-gray-400">{evalMsg}</span>}
            <button
              type="submit"
              disabled={runningEval}
              className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-5 py-2 rounded-lg transition disabled:opacity-50"
            >
              {runningEval ? 'Starting...' : 'Run evaluation'}
            </button>
          </div>
        </form>
      </div>

      {/* Historial */}
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">History</p>
        {evalRuns.length === 0 ? (
          <p className="text-sm text-gray-300">No evaluations run yet.</p>
        ) : (
          <div className="space-y-2">
            {evalRuns.map(r => (
              <div key={r._id} className="border border-gray-100 rounded-lg">
                <div className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition">
                  <button
                    type="button"
                    onClick={() => handleToggleRunDetail(r._id)}
                    className="flex-1 text-left"
                  >
                    <p className="text-sm font-medium text-gray-700">{r.snapshot_name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {r.num_questions} questions · {r.n_exec}x · {r.xai ? 'XAI' : r.retrieval_mode ?? 'naive'} · {new Date(r.created_at).toLocaleString()}
                    </p>
                    {r.status === 'running' && r.progress && (
                      <p className="text-xs text-orange-500 mt-1 animate-pulse">
                        {r.progress.phase === 'queued' && 'Waiting for another evaluation to finish...'}
                        {r.progress.phase === 'indexing' && 'Indexing documents...'}
                        {r.progress.phase === 'querying' && `Step ${r.progress.step}/${r.progress.total} — question ${r.progress.question_num}/${r.progress.n_questions}, run ${r.progress.exec_num}/${r.progress.n_exec}: "${r.progress.question}"`}
                      </p>
                    )}
                  </button>
                  <div className="flex items-center gap-3">
                    {r.status === 'running' && <span className="text-xs text-orange-500 bg-orange-50 px-2 py-1 rounded-full animate-pulse">Running...</span>}
                    {r.status === 'error' && <span className="text-xs text-red-400 bg-red-50 px-2 py-1 rounded-full">Error</span>}
                    <button
                      onClick={() => handleDeleteRun(r._id)}
                      className="text-xs text-red-400 hover:text-red-500 transition"
                    >
                      Delete
                    </button>
                    {r.status === 'done' && (
                      <button
                        onClick={e => { e.stopPropagation(); handleDownloadCSV(r) }}
                        title="Download results as CSV"
                        className="text-gray-400 hover:text-gray-600 transition"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 3v12" />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>

                {expandedRunId === r._id && expandedRunDetail && (
                  <div className="border-t border-gray-100 px-4 py-3 bg-gray-50 space-y-3">
                    {r.status === 'error' && (
                      <p className="text-sm text-red-500">{expandedRunDetail.error}</p>
                    )}
                    {r.rag_config && Object.keys(r.rag_config).length > 0 && (() => {
                      const cfg = r.rag_config
                      const tags = [
                        cfg.retrieval_mode && `retrieval: ${cfg.retrieval_mode}`,
                        cfg.synthesis_mode && `synthesis: ${cfg.synthesis_mode}`,
                        cfg.similarity_top_k != null && `top_k: ${cfg.similarity_top_k}`,
                        cfg.chunk_size != null && `chunk: ${cfg.chunk_size}/${cfg.chunk_overlap ?? 0}`,
                        cfg.temperature != null && `temp: ${cfg.temperature}`,
                        cfg.rerank && `rerank`,
                        cfg.sim_filter && `sim_filter: ${cfg.similarity_cutoff ?? ''}`,
                      ].filter(Boolean)
                      return (
                        <div className="flex flex-wrap gap-1">
                          {tags.map(t => (
                            <span key={t} className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">{t}</span>
                          ))}
                        </div>
                      )
                    })()}
                    {r.status === 'done' && expandedRunDetail.results && (
                      <>
                        <div className="text-xs text-gray-600 grid grid-cols-2 gap-2">
                          <p>Binary score: <b>{expandedRunDetail.results.global.score.mean}</b> (min {expandedRunDetail.results.global.score.min}, max {expandedRunDetail.results.global.score.max})</p>
                          {expandedRunDetail.results.global.avg_rouge1 != null && (() => {
                            const r1 = expandedRunDetail.results.global.avg_rouge1
                            const r2 = expandedRunDetail.results.global.avg_rouge2
                            const rL = expandedRunDetail.results.global.avg_rougeL
                            const color = r1 >= 0.6 ? '#16a34a' : r1 >= 0.4 ? '#f97316' : '#dc2626'
                            return (
                              <p title="Lexical overlap percentage with the expected answer">
                                Quality (ROUGE-1): <b style={{ color }}>{Math.round(r1 * 100)}%</b>
                                <span className="text-gray-400"> · ROUGE-2: {r2} · ROUGE-L: {rL}</span>
                              </p>
                            )
                          })()}
                          {expandedRunDetail.results.global.avg_bertscore != null && (() => {
                            const bs = expandedRunDetail.results.global.avg_bertscore
                            const color = bs >= 0.6 ? '#16a34a' : bs >= 0.4 ? '#f97316' : '#dc2626'
                            return (
                              <p title="Semantic similarity with the expected answer using BERT embeddings">
                                BERTScore: <b style={{ color }}>{Math.round(bs * 100)}%</b>
                              </p>
                            )
                          })()}
                          {r.xai && (
                            <p>Avg. hallucinations: {expandedRunDetail.results.global.avg_hallucinations}</p>
                          )}
                          <p>Time: {expandedRunDetail.results.global.time_seconds}s</p>
                        </div>

                        {/* Score per question line chart */}
                        {(() => {
                          const data = expandedRunDetail.results.per_question
                          const W = 500, H = 148, padL = 30, padR = 10, padT = 26, padB = 24
                          const chartW = W - padL - padR
                          const chartH = H - padT - padB
                          const cx = i => padL + (chartW / (data.length - 1 || 1)) * i
                          const cy = s => padT + chartH * (1 - s)
                          const binPoints = data.map((pq, i) => `${cx(i)},${cy(pq.score.mean)}`).join(' ')
                          const r1Points = data.map((pq, i) => pq.rouge1_mean != null ? `${cx(i)},${cy(pq.rouge1_mean)}` : null).filter(Boolean).join(' ')
                          const bsPoints = data.map((pq, i) => pq.bertscore_mean != null ? `${cx(i)},${cy(pq.bertscore_mean)}` : null).filter(Boolean).join(' ')
                          const hasRouge = data.some(pq => pq.rouge1_mean != null)
                          const hasBert = data.some(pq => pq.bertscore_mean != null)
                          const ticks = [0, 0.5, 1]
                          return (
                            <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 148 }}>
                              {/* Legend */}
                              <circle cx={padL} cy={10} r={3} fill="#fb923c" />
                              <text x={padL + 6} y={13} fontSize="8" fill="#9ca3af">Binary</text>
                              {hasRouge && <>
                                <line x1={padL + 46} y1={10} x2={padL + 56} y2={10} stroke="#60a5fa" strokeWidth="2" />
                                <text x={padL + 60} y={13} fontSize="8" fill="#9ca3af">ROUGE-1</text>
                              </>}
                              {hasBert && <>
                                <line x1={padL + 116} y1={10} x2={padL + 126} y2={10} stroke="#34d399" strokeWidth="2" />
                                <text x={padL + 130} y={13} fontSize="8" fill="#9ca3af">BERTScore</text>
                              </>}
                              {/* Grid */}
                              {ticks.map(t => {
                                const y = cy(t)
                                return (
                                  <g key={t}>
                                    <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="#f3f4f6" strokeWidth="1" />
                                    <text x={padL - 5} y={y + 3} fontSize="8" fill="#9ca3af" textAnchor="end">{t}</text>
                                  </g>
                                )
                              })}
                              {/* Lines */}
                              {hasRouge && <polyline points={r1Points} fill="none" stroke="#60a5fa" strokeWidth="1.5" strokeLinejoin="round" />}
                              {hasBert && <polyline points={bsPoints} fill="none" stroke="#34d399" strokeWidth="1.5" strokeLinejoin="round" />}
                              <polyline points={binPoints} fill="none" stroke="#fb923c" strokeWidth="2" strokeLinejoin="round" />
                              {/* Dots + tooltips */}
                              {data.map((pq, i) => {
                                const score = pq.score.mean
                                const x = cx(i), y = cy(score)
                                const hovered = chartHoveredIdx === i
                                const tooltipLines = [
                                  { label: 'Bin', value: score.toFixed(2), color: '#fb923c' },
                                  pq.rouge1_mean != null && { label: 'R1', value: pq.rouge1_mean.toFixed(2), color: '#60a5fa' },
                                  pq.bertscore_mean != null && { label: 'BS', value: pq.bertscore_mean.toFixed(2), color: '#34d399' },
                                ].filter(Boolean)
                                const ttH = 6 + tooltipLines.length * 11
                                const ttW = 44
                                const tooltipY = Math.max(y - ttH - 4, padT)
                                const tooltipX = Math.min(Math.max(x - ttW / 2, padL), W - padR - ttW)
                                return (
                                  <g key={i} onMouseEnter={() => setChartHoveredIdx(i)} onMouseLeave={() => setChartHoveredIdx(null)} style={{ cursor: 'default' }}>
                                    <circle cx={x} cy={y} r={hovered ? 5 : 3} fill="white" stroke={hovered ? '#f97316' : '#fb923c'} strokeWidth="2" />
                                    <text x={x} y={H - 6} fontSize="8" fill="#9ca3af" textAnchor="middle">Q{i + 1}</text>
                                    {hovered && (
                                      <g>
                                        <rect x={tooltipX} y={tooltipY} width={ttW} height={ttH} fill="#1f2937" rx="3" />
                                        {tooltipLines.map((tl, ti) => (
                                          <text key={ti} x={tooltipX + 4} y={tooltipY + 10 + ti * 11} fontSize="8" fill={tl.color}>{tl.label}: {tl.value}</text>
                                        ))}
                                      </g>
                                    )}
                                  </g>
                                )
                              })}
                              <line x1={padL} y1={padT} x2={padL} y2={padT + chartH} stroke="#e5e7eb" strokeWidth="1" />
                            </svg>
                          )
                        })()}

                        <div className="space-y-2">
                          {expandedRunDetail.results.per_question.map((pq) => (
                            <div key={pq.question} className="bg-white border border-gray-100 rounded-lg px-3 py-2">
                              <p className="text-xs font-medium text-gray-700">{pq.question}</p>
                              <p className="text-xs text-gray-400 mt-1">{pq.last_answer}</p>
                              <p className="text-xs mt-1">
                                {(() => {
                                  const bin = pq.score.mean
                                  const color = bin >= 1 ? '#16a34a' : bin > 0 ? '#f97316' : '#dc2626'
                                  return <span style={{ color }}>Binary: {bin.toFixed(2)}</span>
                                })()}
                                {pq.rouge1_mean != null && (() => {
                                  const color = pq.rouge1_mean >= 0.6 ? '#16a34a' : pq.rouge1_mean >= 0.4 ? '#f97316' : '#dc2626'
                                  return <span style={{ color }}> · Quality: {Math.round(pq.rouge1_mean * 100)}%</span>
                                })()}
                                {pq.bertscore_mean != null && (() => {
                                  const color = pq.bertscore_mean >= 0.6 ? '#16a34a' : pq.bertscore_mean >= 0.4 ? '#f97316' : '#dc2626'
                                  return <span style={{ color }}> · BERTScore: {Math.round(pq.bertscore_mean * 100)}%</span>
                                })()}
                                {r.xai && <span className="text-gray-400"> · Hallucinations {pq.hallucinations_mean}</span>}
                              </p>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  )
}
