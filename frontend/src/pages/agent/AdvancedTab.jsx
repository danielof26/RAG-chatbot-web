import { useState } from 'react'
import { techsFromRagConfig, computeRetrievalMode, computeSynthesisMode, blockedTechsFor, toggleTechSet } from '../../rag/techniques'

export default function AdvancedTab({ agent, id, api, catalog }) {
  const [topK, setTopK] = useState(agent.rag_config?.similarity_top_k ?? 5)
  const [chunkSize, setChunkSize] = useState(agent.rag_config?.chunk_size ?? 512)
  const [chunkOverlap, setChunkOverlap] = useState(agent.rag_config?.chunk_overlap ?? 50)
  const [temperature, setTemperature] = useState(agent.rag_config?.temperature ?? 0.1)
  const [similarityCutoff, setSimilarityCutoff] = useState(agent.rag_config?.similarity_cutoff ?? 0.7)
  const [rerankTopN, setRerankTopN] = useState(agent.rag_config?.rerank_top_n ?? 3)
  const [fusionNumQueries, setFusionNumQueries] = useState(agent.rag_config?.fusion_num_queries ?? 1)
  const [selectedTechs, setSelectedTechs] = useState(techsFromRagConfig(catalog, agent.rag_config))
  const [savingAdvanced, setSavingAdvanced] = useState(false)
  const [advancedSaveMsg, setAdvancedSaveMsg] = useState('')
  const [convMemory, setConvMemory] = useState(agent.rag_config?.conv_memory ?? false)
  const [convMemoryMode, setConvMemoryMode] = useState(agent.rag_config?.conv_memory_mode ?? 'simple')
  const [convMemoryTurns, setConvMemoryTurns] = useState(agent.rag_config?.conv_memory_turns ?? 3)

  const handleSaveAdvanced = async () => {
    if (!catalog) return   // without the catalog the selected mode can't be computed; never overwrite it blindly
    setSavingAdvanced(true)
    setAdvancedSaveMsg('')
    const res = await api.put(`/api/agents/${id}`, {
        rag_config: {
          similarity_top_k: Number(topK),
          chunk_size: Number(chunkSize),
          chunk_overlap: Number(chunkOverlap),
          temperature: Number(temperature),
          retrieval_mode: computeRetrievalMode(catalog, selectedTechs),
          synthesis_mode: computeSynthesisMode(catalog, selectedTechs),
          sim_filter: selectedTechs.has('sim_filter'),
          similarity_cutoff: Number(similarityCutoff),
          rerank: selectedTechs.has('rerank_ce'),
          rerank_top_n: Number(rerankTopN),
          fusion_num_queries: Number(fusionNumQueries),
          xai: selectedTechs.has('xai'),
          long_reorder: selectedTechs.has('long_reorder'),
          conv_memory: convMemory,
          conv_memory_mode: convMemoryMode,
          conv_memory_turns: Number(convMemoryTurns)
        }
      })
    setSavingAdvanced(false)
    setAdvancedSaveMsg(res.ok ? 'Saved!' : 'Error saving')
    if (res.ok) setTimeout(() => setAdvancedSaveMsg(''), 2000)
  }

  const defaultTechs = new Set(catalog?.default_techs ?? [])

  const blockedTechs = catalog ? blockedTechsFor(catalog, selectedTechs) : new Set()

  const toggleTech = (techId) => {
    if (catalog) setSelectedTechs(prev => toggleTechSet(catalog, prev, techId))
  }



  if (!catalog) {
    return <p className="text-sm text-red-400">Could not load the technique catalog. Reload the page to try again.</p>
  }

  return (
    <div className="space-y-4">

      {catalog.sections.map(section => (
        <div key={section.id} className="border border-gray-100 rounded-xl px-5 py-4 space-y-3">

          {/* Section header */}
          <div className="flex items-center gap-2">
            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-orange-50 text-orange-400 text-[10px] font-bold shrink-0">
              {section.num}
            </span>
            <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">{section.title}</p>
          </div>

          <p className="text-xs text-gray-400 leading-relaxed">{section.desc}</p>

          {/* Technique pills */}
          <div className="flex flex-wrap gap-2">
            {section.techniques.map(tech => {
              const selected  = selectedTechs.has(tech.id)
              const blocked   = !selected && blockedTechs.has(tech.id)
              const isDefault = defaultTechs.has(tech.id)
              const clickable = tech.impl && !blocked && !isDefault

              let cls = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors '
              if (selected && isDefault) cls += 'bg-orange-50 text-orange-400 border-orange-100 cursor-default'
              else if (selected)         cls += 'bg-orange-400 text-white border-orange-400 hover:bg-orange-500'
              else if (blocked)          cls += 'bg-white text-gray-300 border-gray-100 cursor-not-allowed opacity-40'
              else if (!tech.impl)       cls += 'bg-white text-gray-300 border-dashed border-gray-200 cursor-not-allowed'
              else                       cls += 'bg-white text-gray-600 border-gray-200 hover:border-orange-300 hover:text-orange-500 cursor-pointer'

              return (
                <button
                  key={tech.id}
                  title={tech.desc}
                  onClick={() => clickable && toggleTech(tech.id)}
                  className={cls}
                  aria-pressed={selected}
                >
                  {tech.label}
                  {!tech.impl && (
                    <span className="text-[9px] bg-gray-100 text-gray-400 px-1.5 py-0.5 rounded-full font-normal">
                      soon
                    </span>
                  )}
                  {blocked && <span className="text-[10px]">🔒</span>}
                </button>
              )
            })}
          </div>

          {/* Retrieval: Top K */}
          {section.id === 'ret' && (
            <div className="pt-1 border-t border-gray-50">
              <label htmlFor="top-k-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1 mt-3">Top K</label>
              <input
                id="top-k-input"
                type="number" min="1" max="50"
                value={topK}
                onChange={e => setTopK(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
              <p className="text-xs text-gray-400 mt-1">Number of chunks fed to the LLM as context per question.</p>
            </div>
          )}

          {/* Retrieval: fusion top_q (only when fusion active) */}
          {section.id === 'ret' && selectedTechs.has('fusion') && (
            <div className="pt-1 border-t border-gray-50">
              <label htmlFor="fusion-num-queries-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1 mt-3">Query Variants (top_q)</label>
              <input
                id="fusion-num-queries-input"
                type="number" min="1" max="8"
                value={fusionNumQueries}
                onChange={e => setFusionNumQueries(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
              <p className="text-xs text-gray-400 mt-1">Number of query variants the LLM generates before fusing results. 1 = no variants (faster), 4 = richer recall.</p>
            </div>
          )}

          {/* Post-retrieval: rerank top_n (only when rerank_ce active) */}
          {section.id === 'post' && selectedTechs.has('rerank_ce') && (
            <div className="pt-1 border-t border-gray-50">
              <label htmlFor="rerank-top-n-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1 mt-3">Reranker top N</label>
              <input
                id="rerank-top-n-input"
                type="number" min="1" max="20"
                value={rerankTopN}
                onChange={e => setRerankTopN(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
              <p className="text-xs text-gray-400 mt-1">Number of chunks the reranker keeps after scoring. Higher = more context, lower = more precision.</p>
            </div>
          )}

          {/* Post-retrieval: similarity cutoff (only when sim_filter active) */}
          {section.id === 'post' && selectedTechs.has('sim_filter') && (
            <div className="pt-1 border-t border-gray-50">
              <label htmlFor="sim-cutoff-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1 mt-3">Similarity threshold</label>
              <input
                id="sim-cutoff-input"
                type="number" min="0" max="1" step="0.05"
                value={similarityCutoff}
                onChange={e => setSimilarityCutoff(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
              <p className="text-xs text-gray-400 mt-1">Chunks with a similarity score below this value are discarded. Between 0 and 1 — try 0.7.</p>
            </div>
          )}

          {/* Chunking: chunk size + overlap */}
          {section.id === 'chunk' && (
            <div className="space-y-3 pt-1 border-t border-gray-50">
              <div className="mt-3">
                <label htmlFor="chunk-size-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Chunk size</label>
                <input
                  id="chunk-size-input"
                  type="number" min="50" max="8000"
                  value={chunkSize}
                  onChange={e => setChunkSize(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                />
                <p className="text-xs text-gray-400 mt-1">Size in tokens of each chunk when indexing documents.</p>
              </div>
              <div>
                <label htmlFor="chunk-overlap-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Chunk overlap</label>
                <input
                  id="chunk-overlap-input"
                  type="number" min="0" max="4000"
                  value={chunkOverlap}
                  onChange={e => setChunkOverlap(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                />
                <p className="text-xs text-gray-400 mt-1">Tokens shared between consecutive chunks to avoid cutting context at boundaries.</p>
              </div>
            </div>
          )}

          {/* Synthesis: temperature */}
          {section.id === 'syn' && (
            <div className="space-y-3 pt-1 border-t border-gray-50">
              <div className="mt-3">
                <label htmlFor="temperature-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Temperature</label>
                <input
                  id="temperature-input"
                  type="number" min="0" max="2" step="0.1"
                  value={temperature}
                  onChange={e => setTemperature(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                />
                <p className="text-xs text-gray-400 mt-1">Lower = more consistent, fact-focused. Higher = more varied, creative.</p>
              </div>
            </div>
          )}

        </div>
      ))}

      {/* Conversational Memory */}
      <div className="border border-gray-100 rounded-xl px-5 py-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-orange-50 text-orange-400 text-[10px] font-bold shrink-0">7</span>
          <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Conversational Memory</p>
        </div>
        <p className="text-xs text-gray-400 leading-relaxed">
          Maintains context across turns so follow-up questions are resolved correctly.
          Simple mode prepends the conversation history to the prompt.
          Condense mode uses the LLM to reformulate the follow-up into a standalone question before retrieval.
        </p>

        {/* Enable toggle */}
        <div className="flex items-center gap-3">
          <input
            id="conv-memory-toggle"
            type="checkbox"
            checked={convMemory}
            onChange={e => setConvMemory(e.target.checked)}
            className="w-4 h-4 accent-orange-400"
          />
          <label htmlFor="conv-memory-toggle" className="text-sm text-gray-600">Enable conversational memory</label>
        </div>

        {convMemory && (
          <div className="space-y-3 pt-1 border-t border-gray-50">
            {/* Mode selector */}
            <div className="mt-3">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Mode</p>
              <div className="flex gap-2">
                {[
                  { id: 'simple',  label: 'Simple',  desc: 'Prepends history to the synthesis prompt. No extra LLM call.' },
                  { id: 'condense', label: 'Condense', desc: 'Reformulates the follow-up into a standalone question before retrieval.' },
                ].map(opt => (
                  <button
                    key={opt.id}
                    title={opt.desc}
                    onClick={() => setConvMemoryMode(opt.id)}
                    className={`px-4 py-2 rounded-full text-xs font-medium border transition-colors ${
                      convMemoryMode === opt.id
                        ? 'bg-orange-400 text-white border-orange-400'
                        : 'bg-white text-gray-600 border-gray-200 hover:border-orange-300 hover:text-orange-500'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Turns input */}
            <div>
              <label htmlFor="conv-memory-turns" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Turns to remember</label>
              <input
                id="conv-memory-turns"
                type="number" min="1" max="10"
                value={convMemoryTurns}
                onChange={e => setConvMemoryTurns(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
              <p className="text-xs text-gray-400 mt-1">Number of previous exchanges included as context (1–10).</p>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-3 pt-2">
        {advancedSaveMsg && <span className="text-sm text-gray-400">{advancedSaveMsg}</span>}
        <button
          onClick={handleSaveAdvanced}
          disabled={savingAdvanced}
          className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-5 py-2 rounded-lg transition disabled:opacity-50"
        >
          {savingAdvanced ? 'Saving...' : 'Save'}
        </button>
      </div>

    </div>
  )
}
