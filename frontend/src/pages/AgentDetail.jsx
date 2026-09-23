// src/pages/AgentDetail.jsx
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const TABS = ['Settings', 'Documents', 'Chat', 'API', 'Advanced', 'Evaluation']

const RAG_SECTIONS = [
  {
    id: 'pre', num: 1,
    title: 'Pre-retrieval · Query transformation',
    desc: 'Applied before the retriever to improve semantic matching. All combinable with each other. The Router is exclusive in index selection but can coexist with the rest.',
    techniques: [
      { id: 'naive',         label: 'Naive (direct)',        impl: true,  desc: 'Uses the question as-is for retrieval. No transformation applied — the baseline. Compatible with CRAG (which also retrieves naively, then filters).',  incompat: ['hyde_answer', 'hyde_combined'] },
      { id: 'hyde_answer',   label: 'HyDE Answer',          impl: true,  desc: 'Generates a hypothetical answer and uses its embedding as the retrieval query.',           incompat: ['naive', 'hyde_combined', 'crag'] },
      { id: 'hyde_combined', label: 'HyDE Combined',        impl: true,  desc: 'Embeds both the original question and a hypothetical answer for retrieval.',               incompat: ['naive', 'hyde_answer',   'crag'] },
      { id: 'multi_query',   label: 'Multi-Query',          impl: false, desc: 'Generates N reformulations of the question and fuses all results to improve recall.',     incompat: [] },
      { id: 'step_back',     label: 'Step-back Prompting',  impl: false, desc: 'Abstracts the question to a higher-level concept before retrieving.',                     incompat: [] },
      { id: 'sub_question',  label: 'Sub-question Engine',  impl: false, desc: 'Decomposes complex questions into sub-questions, each with its own retrieval.',           incompat: [] },
      { id: 'router',        label: 'Router Adaptativo',    impl: true,  desc: 'Classifies the query type (factual, multi-hop, summary, out-of-domain) and routes it to the most suitable engine automatically.',        incompat: ['hyde_answer', 'hyde_combined', 'crag', 'self_rag'] },
    ]
  },
  {
    id: 'idx', num: 2,
    title: 'Indexing · Knowledge base structure',
    desc: 'How documents are organized in the index. Choose one per collection — mutually exclusive.',
    techniques: [
      { id: 'vector_index',  label: 'Vector Store Index',    impl: true,  desc: 'Dense semantic index — the standard choice for most RAG pipelines.',      incompat: ['summary_index','tree_index','keyword_index','kg_index'] },
      { id: 'summary_index', label: 'Summary Index (List)',  impl: false, desc: 'Indexes document summaries, useful for high-level summarization queries.', incompat: ['vector_index','tree_index','keyword_index','kg_index'] },
      { id: 'tree_index',    label: 'Tree Index',            impl: false, desc: 'Hierarchical index built by recursively summarizing chunks up a tree.',    incompat: ['vector_index','summary_index','keyword_index','kg_index'] },
      { id: 'keyword_index', label: 'Keyword Table Index',   impl: false, desc: 'Keyword-based index, precise for exact-match technical retrieval.',        incompat: ['vector_index','summary_index','tree_index','kg_index'] },
      { id: 'kg_index',      label: 'Knowledge Graph Index', impl: false, desc: 'Graph-based index for documents with rich entity relationships.',          incompat: ['vector_index','summary_index','tree_index','keyword_index'] },
    ]
  },
  {
    id: 'chunk', num: 3,
    title: 'Chunking · Document preprocessing',
    desc: 'How documents are split before indexing. Choose one. Changes apply only when re-indexing.',
    techniques: [
      { id: 'fixed_size',     label: 'Fixed-size',            impl: true,  desc: 'Splits by token count. Configure size and overlap in the fields below.',    incompat: ['sent_window','semantic_chunk','hierarchical'] },
      { id: 'sent_window',    label: 'Sentence window',       impl: false, desc: 'Chunks by sentence and retrieves with a surrounding context window.',       incompat: ['fixed_size','semantic_chunk','hierarchical'] },
      { id: 'semantic_chunk', label: 'Semantic chunking',     impl: false, desc: 'Splits at semantic boundaries detected by embedding similarity.',           incompat: ['fixed_size','sent_window','hierarchical'] },
      { id: 'hierarchical',   label: 'Hierarchical chunking', impl: false, desc: 'Creates chunks at multiple granularity levels (parent + child nodes).',    incompat: ['fixed_size','sent_window','semantic_chunk'] },
    ]
  },
  {
    id: 'ret', num: 4,
    title: 'Retrieval · Retriever strategy',
    desc: 'How relevant nodes are searched within the index. All combinable — Fusion is literally dense + sparse together.',
    techniques: [
      { id: 'vec_retriever',  label: 'Vector Store (dense)',    impl: true,  desc: 'Semantic similarity search using embeddings — the standard retriever.',     incompat: [] },
      { id: 'bm25',           label: 'BM25 (sparse/keyword)',   impl: false, desc: 'Classic keyword retrieval — complements dense search for exact terms.',    incompat: [] },
      { id: 'auto_merging',   label: 'Auto-Merging',            impl: false, desc: 'Merges child chunks into parent when enough siblings are retrieved.',      incompat: [] },
      { id: 'recursive',      label: 'Recursive Retriever',     impl: false, desc: 'Follows references between nodes recursively to complete context.',       incompat: [] },
      { id: 'fusion',         label: 'Fusion (dense + sparse)', impl: true,  desc: 'Combines vector and BM25 retrievers with reciprocal rank fusion for hybrid retrieval.',  incompat: ['hyde_answer', 'hyde_combined', 'crag', 'self_rag', 'router'] },
      { id: 'auto_retrieval', label: 'Auto-Retrieval',          impl: false, desc: 'Extracts metadata filters from the query to narrow the search space.',   incompat: [] },
    ]
  },
  {
    id: 'post', num: 5,
    title: 'Post-retrieval · Filtering & reranking',
    desc: 'Applied after retrieval to improve chunk quality. Most are combinable in pipeline — except the two reranking methods, choose one.',
    techniques: [
      { id: 'crag',         label: 'CRAG — Corrective RAG',    impl: true,  desc: 'LLM grades each chunk as relevant/ambiguous/irrelevant and filters the irrelevant ones.', incompat: ['rerank_ce','rerank_llm','hyde_answer','hyde_combined'] },
      { id: 'self_rag',    label: 'Self-RAG',                 impl: true,  desc: 'After generating, the LLM evaluates its own answer (PASS/FAIL). If FAIL, retries with chunks embedded directly in the prompt.', incompat: [] },
      { id: 'rerank_ce',    label: 'Reranking (cross-encoder)', impl: true, desc: 'Reranks chunks using a sentence-transformer cross-encoder model.',       incompat: ['crag','rerank_llm'] },
      { id: 'rerank_llm',   label: 'Reranking (LLM)',          impl: false, desc: 'Reranks chunks by asking the LLM to score each one for relevance.',     incompat: ['crag','rerank_ce'] },
      { id: 'sim_filter',   label: 'SimilarityPostprocessor',  impl: true,  desc: 'Discards chunks whose similarity score is below a set threshold.',       incompat: [] },
      { id: 'kw_filter',    label: 'KeywordNodePostprocessor', impl: false, desc: 'Filters chunks that do not contain required keywords.',                  incompat: [] },
      { id: 'prev_next',    label: 'PrevNextNodePostprocessor',impl: false, desc: 'Expands each retrieved chunk with its neighbouring chunks for context.', incompat: [] },
      { id: 'long_reorder', label: 'LongContextReorder',       impl: false, desc: 'Reorders chunks to place the most relevant at start and end of prompt.',incompat: [] },
    ]
  },
  {
    id: 'syn', num: 6,
    title: 'Response synthesis',
    desc: 'How retrieved chunks are assembled into the final answer. Choose one — mutually exclusive.',
    techniques: [
      { id: 'compact',          label: 'Compact (default)', impl: true,  desc: 'Packs chunks into the fewest possible LLM prompts before generating.',           incompat: ['refine','tree_summarize','simple_summarize','accumulate'] },
      { id: 'refine',           label: 'Refine',            impl: true, desc: 'Iteratively refines the answer chunk by chunk.',                                 incompat: ['compact','tree_summarize','simple_summarize','accumulate'] },
      { id: 'tree_summarize',   label: 'Tree Summarize',    impl: true, desc: 'Builds a summary tree bottom-up — best for very long documents.',                incompat: ['compact','refine','simple_summarize','accumulate'] },
      { id: 'simple_summarize', label: 'Simple Summarize',  impl: true, desc: 'Truncates all chunks into a single prompt — fastest but may lose information.', incompat: ['compact','refine','tree_summarize','accumulate'] },
      { id: 'accumulate',       label: 'Accumulate',        impl: true, desc: 'Generates an answer per chunk independently, then combines them.',               incompat: ['compact','refine','tree_summarize','simple_summarize'] },
    ]
  },
]

const DEFAULT_TECHS = new Set(['vector_index', 'vec_retriever', 'fixed_size'])

const MODE_TECHS = {
  naive:         ['naive',             'compact'],
  crag:          ['naive', 'crag',     'compact'],
  hyde_answer:   ['hyde_answer',       'compact'],
  hyde_combined: ['hyde_combined',     'compact'],
  self_rag:      ['naive', 'self_rag', 'compact'],
  router:        ['router',            'compact'],
  fusion:        ['fusion',            'compact'],
}

const initTechsFromMode = (mode) => {
  const t = new Set(DEFAULT_TECHS)
  ;(MODE_TECHS[mode] ?? ['naive']).forEach(id => t.add(id))
  return t
}

const MODE_PRIORITY = ['crag', 'self_rag', 'router', 'fusion', 'hyde_combined', 'hyde_answer', 'naive']

const computeRetrievalMode = (techs) =>
  MODE_PRIORITY.find(mode => techs.has(mode)) ?? 'naive'

const SYNTHESIS_PRIORITY = ['refine', 'tree_summarize', 'simple_summarize', 'accumulate', 'compact']

const computeSynthesisMode = (techs) =>
  SYNTHESIS_PRIORITY.find(mode => techs.has(mode)) ?? 'compact'

export default function AgentDetail() {
  const { id } = useParams()
  const { token } = useAuth()
  const navigate = useNavigate()
  const fileRef = useRef()

  const [agent, setAgent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('Settings')

  // Settings
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [prompt, setPrompt] = useState('')
  const [llmServerId, setLlmServerId] = useState('')
  const [llmModel, setLlmModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')

  // LLM servers & models
  const [llmServers, setLlmServers] = useState([])
  const [availableModels, setAvailableModels] = useState([])
  const [loadingModels, setLoadingModels] = useState(false)

  // Embed server & model
  const [embedServerId, setEmbedServerId] = useState('')
  const [embedModel, setEmbedModel] = useState('')
  const [availableEmbedModels, setAvailableEmbedModels] = useState([])
  const [loadingEmbedModels, setLoadingEmbedModels] = useState(false)
  const [savingEmbed, setSavingEmbed] = useState(false)
  const [embedSaveMsg, setEmbedSaveMsg] = useState('')

  // API Keys
  const [apiKeyRequired, setApiKeyRequired] = useState(false)
  const [apiKeys, setApiKeys] = useState([])
  const [newKeyName, setNewKeyName] = useState('')
  const [createdKey, setCreatedKey] = useState(null)
  const [savingApi, setSavingApi] = useState(false)

  // Advanced (RAG config)
  const [topK, setTopK] = useState(5)
  const [chunkSize, setChunkSize] = useState(512)
  const [chunkOverlap, setChunkOverlap] = useState(50)
  const [temperature, setTemperature] = useState(0.1)
  const [similarityCutoff, setSimilarityCutoff] = useState(0.7)
  const [rerankTopN, setRerankTopN] = useState(3)
  const [fusionNumQueries, setFusionNumQueries] = useState(1)
  const [selectedTechs, setSelectedTechs] = useState(() => initTechsFromMode('naive'))
  const [savingAdvanced, setSavingAdvanced] = useState(false)
  const [advancedSaveMsg, setAdvancedSaveMsg] = useState('')

  // Documents
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [indexingMsg, setIndexingMsg] = useState('')

  // Evaluation
  const [snapshots, setSnapshots] = useState([])
  const [newSnapshotName, setNewSnapshotName] = useState('')
  const [evalSnapshotId, setEvalSnapshotId] = useState('')
  const [evalLanguage, setEvalLanguage] = useState('en')
  const [evalNExec, setEvalNExec] = useState(3)
  const [evalXai, setEvalXai] = useState(false)
  const [runningEval, setRunningEval] = useState(false)
  const [evalMsg, setEvalMsg] = useState('')
  const [evalRuns, setEvalRuns] = useState([])
  const [expandedRunId, setExpandedRunId] = useState('')
  const [expandedRunDetail, setExpandedRunDetail] = useState(null)
  const [chartHoveredIdx, setChartHoveredIdx] = useState(null)
  const evalFileRef = useRef()

  // Chat
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = useRef()

  useEffect(() => { fetchAgent() }, [id])
  useEffect(() => { fetchLlmServers() }, [])
  useEffect(() => { if (activeTab === 'API') fetchApiKeys() }, [activeTab])
  useEffect(() => { if (activeTab === 'Chat') fetchChatHistory() }, [activeTab])
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => {
    if (activeTab === 'Evaluation') { fetchSnapshots(); fetchEvalRuns() }
  }, [activeTab])

  // Auto-refresh mientras haya alguna evaluación en curso (rápido, para mostrar avance paso a paso)
  useEffect(() => {
    const hasRunning = evalRuns.some(r => r.status === 'running')
    if (!hasRunning) return
    const interval = setInterval(fetchEvalRuns, 3000)
    return () => clearInterval(interval)
  }, [evalRuns])

  // Cuando cambia el servidor seleccionado, carga sus modelos
  useEffect(() => {
    if (!llmServerId) { setAvailableModels([]); return }
    const load = async () => {
      setLoadingModels(true)
      const res = await fetch(`/api/llm-servers/${llmServerId}/models`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await res.json()
      setAvailableModels(res.ok ? data.models : [])
      setLoadingModels(false)
    }
    load()
  }, [llmServerId])

  // Cuando cambia el servidor de embeddings, carga sus modelos
  useEffect(() => {
    if (!embedServerId) { setAvailableEmbedModels([]); return }
    const load = async () => {
      setLoadingEmbedModels(true)
      const res = await fetch(`/api/llm-servers/${embedServerId}/models`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const data = await res.json()
      setAvailableEmbedModels(res.ok ? data.models : [])
      setLoadingEmbedModels(false)
    }
    load()
  }, [embedServerId])

  // Auto-refresh mientras haya documentos pendientes o indexando
  useEffect(() => {
    const hasPending = agent?.documents?.some(d => d.status === 'pending' || d.status === 'indexing')
    if (!hasPending) return
    const interval = setInterval(fetchDocuments, 10000)
    return () => clearInterval(interval)
  }, [agent])

  const fetchAgent = async () => {
    const res = await fetch(`/api/agents/${id}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) { navigate('/agents'); return }
    const data = await res.json()
    setAgent(data)
    setName(data.name || '')
    setDescription(data.description || '')
    setPrompt(data.prompt || '')
    setLlmServerId(data.llm_server_id || '')
    setLlmModel(data.llm_model || '')
    setEmbedServerId(data.embed_server_id || '')
    setEmbedModel(data.embed_model || '')
    setApiKeyRequired(data.api_key_required || false)
    setTopK(data.rag_config?.similarity_top_k ?? 5)
    setChunkSize(data.rag_config?.chunk_size ?? 512)
    setChunkOverlap(data.rag_config?.chunk_overlap ?? 50)
    setTemperature(data.rag_config?.temperature ?? 0.1)
    setSimilarityCutoff(data.rag_config?.similarity_cutoff ?? 0.7)
    setRerankTopN(data.rag_config?.rerank_top_n ?? 3)
    setFusionNumQueries(data.rag_config?.fusion_num_queries ?? 1)
    const techs = initTechsFromMode(data.rag_config?.retrieval_mode ?? 'naive')
    const synthMode = data.rag_config?.synthesis_mode ?? 'compact'
    if (synthMode !== 'compact') { techs.delete('compact'); techs.add(synthMode) }
    if (data.rag_config?.sim_filter) techs.add('sim_filter')
    if (data.rag_config?.rerank)     techs.add('rerank_ce')
    setSelectedTechs(techs)
    setLoading(false)
  }

  const fetchDocuments = async () => {
    const res = await fetch(`/api/agents/${id}/documents`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) return
    const documents = await res.json()
    setAgent(prev => prev && { ...prev, documents })
  }

  const fetchLlmServers = async () => {
    const res = await fetch('/api/llm-servers', {
      headers: { Authorization: `Bearer ${token}` }
    })
    const data = await res.json()
    setLlmServers(res.ok ? data : [])
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveMsg('')
    const res = await fetch(`/api/agents/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        name, description, prompt,
        llm_server_id: llmServerId || null,
        llm_model: llmModel,
        api_key_required: apiKeyRequired
      })
    })
    setSaving(false)
    if (res.ok) {
      setSaveMsg('Saved!')
      setTimeout(() => setSaveMsg(''), 2000)
    } else {
      setSaveMsg('Error saving')
    }
  }

  const handleDelete = async () => {
    if (!globalThis.confirm('Delete this agent? This cannot be undone.')) return
    await fetch(`/api/agents/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    })
    navigate('/agents')
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    setUploadMsg('')
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`/api/agents/${id}/documents`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form
    })
    const data = await res.json()
    setUploading(false)
    setUploadMsg(res.ok ? data.message : data.error)
    if (res.ok) await fetchDocuments()
    fileRef.current.value = ''
  }

  const handleDeleteDocument = async (filename) => {
    if (!globalThis.confirm(`Delete "${filename}"? This cannot be undone.`)) return
    const res = await fetch(`/api/agents/${id}/documents/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.ok) await fetchDocuments()
  }

  const handleIndex = async (filename) => {
    setIndexingMsg('')
    const res = await fetch(`/api/agents/${id}/documents/${encodeURIComponent(filename)}/index`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    })
    const data = await res.json()
    setIndexingMsg(res.ok ? data.message : data.error)
    if (res.ok) await fetchDocuments()
  }

  const fetchApiKeys = async () => {
    const res = await fetch(`/api/agents/${id}/api-keys`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.ok) setApiKeys(await res.json())
  }

  const handleCreateKey = async () => {
    const res = await fetch(`/api/agents/${id}/api-keys`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: newKeyName.trim() || undefined })
    })
    if (!res.ok) return
    const created = await res.json()
    setCreatedKey(created)
    setNewKeyName('')
    await fetchApiKeys()
  }

  const handleDeleteKey = async (keyId) => {
    if (!globalThis.confirm('Delete this API key? This cannot be undone.')) return
    await fetch(`/api/agents/${id}/api-keys/${keyId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    })
    await fetchApiKeys()
  }

  const handleSaveEmbedSettings = async () => {
    setSavingEmbed(true)
    setEmbedSaveMsg('')
    const res = await fetch(`/api/agents/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        embed_server_id: embedServerId || null,
        embed_model: embedModel
      })
    })
    setSavingEmbed(false)
    setEmbedSaveMsg(res.ok ? 'Saved!' : 'Error saving')
    if (res.ok) setTimeout(() => setEmbedSaveMsg(''), 2000)
  }

  const handleSaveApiSettings = async () => {
    setSavingApi(true)
    await fetch(`/api/agents/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ api_key_required: apiKeyRequired })
    })
    setSavingApi(false)
  }

  const handleSaveAdvanced = async () => {
    setSavingAdvanced(true)
    setAdvancedSaveMsg('')
    const res = await fetch(`/api/agents/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        rag_config: {
          similarity_top_k: Number(topK),
          chunk_size: Number(chunkSize),
          chunk_overlap: Number(chunkOverlap),
          temperature: Number(temperature),
          retrieval_mode: computeRetrievalMode(selectedTechs),
          synthesis_mode: computeSynthesisMode(selectedTechs),
          sim_filter: selectedTechs.has('sim_filter'),
          similarity_cutoff: Number(similarityCutoff),
          rerank: selectedTechs.has('rerank_ce'),
          rerank_top_n: Number(rerankTopN),
          fusion_num_queries: Number(fusionNumQueries)
        }
      })
    })
    setSavingAdvanced(false)
    setAdvancedSaveMsg(res.ok ? 'Saved!' : 'Error saving')
    if (res.ok) setTimeout(() => setAdvancedSaveMsg(''), 2000)
  }

  const fetchSnapshots = async () => {
    const res = await fetch(`/api/agents/${id}/config-snapshots`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.ok) setSnapshots(await res.json())
  }

  const handleCreateSnapshot = async () => {
    await fetch(`/api/agents/${id}/config-snapshots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: newSnapshotName.trim() || undefined })
    })
    setNewSnapshotName('')
    await fetchSnapshots()
  }

  const handleDeleteSnapshot = async (snapshotId) => {
    if (!globalThis.confirm('Delete this saved configuration? This cannot be undone.')) return
    await fetch(`/api/agents/${id}/config-snapshots/${snapshotId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    })
    await fetchSnapshots()
  }

  const fetchEvalRuns = async () => {
    const res = await fetch(`/api/agents/${id}/evaluations`, {
      headers: { Authorization: `Bearer ${token}` }
    })
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
    form.append('xai', evalXai)

    const res = await fetch(`/api/agents/${id}/evaluations`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form
    })
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
    const res = await fetch(`/api/agents/${id}/evaluations/${runId}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.ok) setExpandedRunDetail(await res.json())
  }

  const handleDeleteRun = async (runId) => {
    if (!globalThis.confirm('Delete this evaluation run? This cannot be undone.')) return
    await fetch(`/api/agents/${id}/evaluations/${runId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    })
    if (expandedRunId === runId) { setExpandedRunId(''); setExpandedRunDetail(null) }
    await fetchEvalRuns()
  }

  const fetchChatHistory = async () => {
    setLoadingHistory(true)
    const res = await fetch(`/api/agents/${id}/chat/history`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.ok) {
      const history = await res.json()
      setMessages(history.map(m => ({ ...m, key: m._id })))
    }
    setLoadingHistory(false)
  }

  const handleClearChat = async () => {
    if (!globalThis.confirm('Clear the whole conversation? This cannot be undone.')) return
    await fetch(`/api/agents/${id}/chat/history`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    })
    setMessages([])
  }

  const handleChat = async (e) => {
    e.preventDefault()
    if (!question.trim()) return
    const askedQuestion = question
    setQuestion('')
    setMessages(prev => [...prev, { role: 'user', content: askedQuestion, key: `${Date.now()}-${Math.random().toString(36).slice(2)}` }])
    setChatLoading(true)
    const res = await fetch(`/api/agents/${id}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ question: askedQuestion })
    })
    const data = await res.json()
    setChatLoading(false)
    setMessages(prev => [...prev, { role: 'assistant', content: res.ok ? data.answer : data.error, key: `${Date.now()}-${Math.random().toString(36).slice(2)}` }])
  }

  const blockedTechs = new Set()
  RAG_SECTIONS.forEach(s => s.techniques.forEach(t => {
    if (selectedTechs.has(t.id)) t.incompat.forEach(id => blockedTechs.add(id))
  }))

  const toggleTech = (techId) => {
    if (DEFAULT_TECHS.has(techId)) return
    let tech = null
    for (const s of RAG_SECTIONS) {
      const found = s.techniques.find(t => t.id === techId)
      if (found) { tech = found; break }
    }
    if (!tech?.impl) return
    setSelectedTechs(prev => {
      const next = new Set(prev)
      if (next.has(techId)) { next.delete(techId) }
      else { tech.incompat.forEach(id => next.delete(id)); next.add(techId) }
      return next
    })
  }

  if (loading) return <div className="min-h-screen flex items-center justify-center text-sm text-gray-400">Loading...</div>

  return (
    <div className="min-h-screen bg-white">

      {/* Header */}
      <div className="border-b border-gray-100 px-8 py-4 flex items-center gap-4">
        <button
          onClick={() => navigate('/agents')}
          className="text-sm text-gray-400 hover:text-gray-600 transition"
        >
          ← Back
        </button>
        <h1 className="text-lg font-semibold text-gray-800">{agent.name}</h1>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-100 px-8">
        <div className="flex gap-6">
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-3 text-sm font-medium border-b-2 transition ${
                activeTab === tab
                  ? 'border-orange-400 text-orange-500'
                  : 'border-transparent text-gray-400 hover:text-gray-600'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Contenido */}
      <div className="max-w-2xl mx-auto px-8 py-10">

        {/* ── SETTINGS ── */}
        {activeTab === 'Settings' && (
          <div className="space-y-5">
            <div>
              <label htmlFor="agent-name" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Name</label>
              <input
                id="agent-name"
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </div>
            <div>
              <label htmlFor="agent-description" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Description</label>
              <input
                id="agent-description"
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="What does this agent do?"
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </div>
            <div>
              <label htmlFor="agent-prompt" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">System prompt</label>
              <textarea
                id="agent-prompt"
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                rows={5}
                placeholder="You are an assistant that..."
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 resize-none"
              />
            </div>

            {/* LLM Server selector */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label htmlFor="llm-server-select" className="block text-xs font-medium text-gray-500 uppercase tracking-wide">LLM Server</label>
                <button
                  type="button"
                  onClick={() => navigate('/llm-servers')}
                  className="text-xs text-orange-400 hover:text-orange-500 transition"
                >
                  Manage servers →
                </button>
              </div>
              <select
                id="llm-server-select"
                value={llmServerId}
                onChange={e => { setLlmServerId(e.target.value); setLlmModel('') }}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 bg-white"
              >
                <option value="">— No server configured —</option>
                {llmServers.map(s => (
                  <option key={s._id} value={s._id}>{s.name} ({s.type})</option>
                ))}
              </select>
            </div>

            {/* Model selector */}
            {llmServerId && (
              <div>
                <label htmlFor="llm-model-select" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Model</label>
                {loadingModels && (
                  <p className="text-sm text-gray-400 animate-pulse">Loading models...</p>
                )}
                {!loadingModels && (
                  <>
                    <input
                      id="llm-model-select"
                      list="llm-model-options"
                      value={llmModel}
                      onChange={e => setLlmModel(e.target.value)}
                      placeholder="Select or type a model name"
                      className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                    />
                    <datalist id="llm-model-options">
                      {availableModels.map(m => (
                        <option key={m} value={m} />
                      ))}
                    </datalist>
                  </>
                )}
              </div>
            )}


            <div className="flex items-center justify-between pt-2">
              <button
                onClick={handleDelete}
                className="text-sm text-red-400 hover:text-red-500 transition"
              >
                Delete agent
              </button>
              <div className="flex items-center gap-3">
                {saveMsg && <span className="text-sm text-gray-400">{saveMsg}</span>}
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-5 py-2 rounded-lg transition disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── DOCUMENTS ── */}
        {activeTab === 'Documents' && (
          <div>
            {/* Embedding Server selector */}
            <div className="mb-6 border border-gray-100 rounded-xl px-5 py-4">
              <div className="flex items-center justify-between mb-1">
                <label htmlFor="embed-server-select" className="block text-xs font-medium text-gray-500 uppercase tracking-wide">Embedding Server</label>
                <button
                  type="button"
                  onClick={() => navigate('/llm-servers')}
                  className="text-xs text-orange-400 hover:text-orange-500 transition"
                >
                  Manage servers →
                </button>
              </div>
              <p className="text-xs text-gray-400 mb-3">
                Used to generate embeddings when indexing or querying documents for this agent.
                Make sure the model you pick below actually supports embeddings on this server —
                not every model does (e.g. chat-only models will fail).
              </p>
              <select
                id="embed-server-select"
                value={embedServerId}
                onChange={e => { setEmbedServerId(e.target.value); setEmbedModel('') }}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 bg-white mb-3"
              >
                <option value="">— Select an embedding server (required) —</option>
                {llmServers.map(s => (
                  <option key={s._id} value={s._id}>{s.name} ({s.type})</option>
                ))}
              </select>

              {/* Embedding Model selector */}
              {embedServerId && (
                <div className="mb-3">
                  <label htmlFor="embed-model-select" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Embedding Model</label>
                  {loadingEmbedModels && (
                    <p className="text-sm text-gray-400 animate-pulse">Loading models...</p>
                  )}
                  {!loadingEmbedModels && (
                    <>
                      <input
                        id="embed-model-select"
                        list="embed-model-options"
                        value={embedModel}
                        onChange={e => setEmbedModel(e.target.value)}
                        placeholder="Select or type a model name"
                        className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                      />
                      <datalist id="embed-model-options">
                        {availableEmbedModels.map(m => (
                          <option key={m} value={m} />
                        ))}
                      </datalist>
                    </>
                  )}
                </div>
              )}

              <div className="flex items-center justify-end gap-3">
                {embedSaveMsg && <span className="text-sm text-gray-400">{embedSaveMsg}</span>}
                <button
                  onClick={handleSaveEmbedSettings}
                  disabled={savingEmbed}
                  className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition disabled:opacity-50"
                >
                  {savingEmbed ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>

            <div className="mb-6">
              <input type="file" ref={fileRef} onChange={handleUpload} className="hidden" />
              <button
                onClick={() => fileRef.current.click()}
                disabled={uploading}
                className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition disabled:opacity-50"
              >
                {uploading ? 'Uploading...' : '+ Upload document'}
              </button>
              {uploadMsg && <p className="text-sm text-gray-400 mt-2">{uploadMsg}</p>}
            </div>

            {indexingMsg && <p className="text-sm text-gray-400 mb-4">{indexingMsg}</p>}

            {agent.documents?.length === 0 ? (
              <p className="text-sm text-gray-300">No documents uploaded yet.</p>
            ) : (
              <div className="space-y-2">
                {agent.documents?.map((doc) => (
                  <div key={doc.filename} className="flex flex-col border border-gray-100 rounded-lg px-4 py-3 gap-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-gray-300">📄</span>
                        <span className="text-sm text-gray-600">{doc.filename}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        {doc.status === 'pending'  && <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">Pending</span>}
                        {doc.status === 'indexing' && <span className="text-xs text-orange-500 bg-orange-50 px-2 py-1 rounded-full animate-pulse">Indexing...</span>}
                        {doc.status === 'indexed'  && <span className="text-xs text-green-500 bg-green-50 px-2 py-1 rounded-full">Indexed</span>}
                        {doc.status === 'error'    && <span className="text-xs text-red-400 bg-red-50 px-2 py-1 rounded-full">Error</span>}
                        {doc.status === 'error' && (
                          <button
                            onClick={() => handleIndex(doc.filename)}
                            className="text-xs bg-orange-400 hover:bg-orange-500 text-white px-3 py-1 rounded-lg transition"
                          >
                            Retry
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteDocument(doc.filename)}
                          className="text-xs text-red-400 hover:text-red-500 transition"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                    {doc.status === 'error' && doc.error && (
                      <p className="text-xs text-red-400 pl-7">{doc.error}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── CHAT ── */}
        {activeTab === 'Chat' && (
          <div>
            {messages.length > 0 && (
              <div className="flex justify-end mb-3">
                <button
                  onClick={handleClearChat}
                  className="text-xs text-gray-400 hover:text-red-500 transition"
                >
                  Clear chat
                </button>
              </div>
            )}

            <div className="max-h-[60vh] overflow-y-auto space-y-4 mb-6 pr-1">
              {loadingHistory && (
                <p className="text-sm text-gray-300">Loading conversation...</p>
              )}

              {!loadingHistory && messages.length === 0 && (
                <p className="text-sm text-gray-300">Ask something about your documents to start the conversation.</p>
              )}

              {messages.map(m => (
                <div key={m.key} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] rounded-xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                    m.role === 'user'
                      ? 'bg-orange-400 text-white'
                      : 'bg-gray-50 border border-gray-100 text-gray-700'
                  }`}>
                    {m.content}
                  </div>
                </div>
              ))}

              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-50 border border-gray-100 rounded-xl px-4 py-3 text-sm text-gray-400 animate-pulse">
                    Thinking...
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            <form onSubmit={handleChat} className="flex gap-3">
              <input
                value={question}
                onChange={e => setQuestion(e.target.value)}
                placeholder="Ask something about your documents..."
                className="flex-1 border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
              <button
                type="submit"
                disabled={chatLoading || !question.trim()}
                className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-5 py-2 rounded-lg transition disabled:opacity-50"
              >
                {chatLoading ? '...' : 'Ask'}
              </button>
            </form>
          </div>
        )}

        {/* ── API ── */}
        {activeTab === 'API' && (
          <div className="space-y-8">

            {/* Protección por API Key */}
            <div className="flex items-center justify-between border border-gray-100 rounded-xl px-5 py-4">
              <div>
                <p className="text-sm font-medium text-gray-700">Protect with API Key</p>
                <p className="text-xs text-gray-400 mt-0.5">If enabled, only requests with a valid key will be answered.</p>
              </div>
              <div className="flex items-center gap-3">
                <input
                  id="api-key-required"
                  type="checkbox"
                  checked={apiKeyRequired}
                  onChange={e => setApiKeyRequired(e.target.checked)}
                  className="w-4 h-4 accent-orange-400"
                />
                <button
                  onClick={handleSaveApiSettings}
                  disabled={savingApi}
                  className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition disabled:opacity-50"
                >
                  {savingApi ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>

            {/* Explicación en lenguaje sencillo */}
            <div className="bg-blue-50 border border-blue-100 rounded-xl px-5 py-4">
              <p className="text-sm font-medium text-blue-800 mb-2">How to use this</p>
              <p className="text-sm text-blue-700 leading-relaxed">
                This lets you talk to this agent from outside this website — for example from
                another app, a script, or an automation tool like n8n or Postman.
                Send a request to the URL below with your question, and you'll get the agent's
                answer back.
              </p>
              {apiKeyRequired && (
                <p className="text-sm text-blue-700 leading-relaxed mt-2">
                  Since protection is enabled, every request must also include a header named{' '}
                  <code className="bg-blue-100 px-1 rounded">X-API-Key</code> with the value of one
                  of the keys generated below — think of it as a password that proves the request
                  is allowed to use this agent. Without it (or with a wrong/deleted key), the
                  request will be rejected.
                </p>
              )}
            </div>

            {/* Documentación del endpoint */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Endpoint</p>
                <a
                  href={`/docs/${id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs bg-orange-400 hover:bg-orange-500 text-white px-3 py-1.5 rounded-lg transition"
                >
                  Try →
                </a>
              </div>
              <div className="bg-gray-50 border border-gray-100 rounded-xl px-5 py-4 space-y-3 font-mono text-xs text-gray-600">
                <p><span className="text-orange-500 font-semibold">POST</span> <span className="text-gray-800">/api/public/agents/{id}/chat</span></p>
                <div>
                  <p className="text-gray-400 mb-1">Headers:</p>
                  <p className="pl-4">Content-Type: application/json</p>
                  {apiKeyRequired && <p className="pl-4">X-API-Key: {'<your_api_key>'}</p>}
                </div>
                <div>
                  <p className="text-gray-400 mb-1">Body:</p>
                  <p className="pl-4">{'{ "question": "your question" }'}</p>
                </div>
                <div>
                  <p className="text-gray-400 mb-1">Response:</p>
                  <p className="pl-4">{'{ "answer": "..." }'}</p>
                </div>
              </div>
            </div>

            {/* Gestión de claves */}
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">API Keys</p>

              {/* Crear nueva clave */}
              <div className="flex gap-2 mb-4">
                <input
                  value={newKeyName}
                  onChange={e => setNewKeyName(e.target.value)}
                  placeholder="Key name (optional)"
                  className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                />
                <button
                  onClick={handleCreateKey}
                  className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition"
                >
                  + Generate key
                </button>
              </div>

              {/* Clave recién creada (mostrar completa solo una vez) */}
              {createdKey && (
                <div className="mb-4 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
                  <p className="text-xs font-medium text-green-700 mb-1">Key created — copy it now, it won't be shown again:</p>
                  <p className="font-mono text-xs text-green-800 break-all">{createdKey.key}</p>
                  <button onClick={() => setCreatedKey(null)} className="text-xs text-green-600 hover:text-green-700 mt-2">Dismiss</button>
                </div>
              )}

              {/* Lista de claves */}
              {apiKeys.length === 0 ? (
                <p className="text-sm text-gray-300">No API keys yet.</p>
              ) : (
                <div className="space-y-2">
                  {apiKeys.map(k => (
                    <div key={k._id} className="flex items-center justify-between border border-gray-100 rounded-lg px-4 py-3">
                      <div>
                        <p className="text-sm text-gray-700">{k.name}</p>
                        <p className="font-mono text-xs text-gray-400">{k.key}</p>
                      </div>
                      <button
                        onClick={() => handleDeleteKey(k._id)}
                        className="text-xs text-red-400 hover:text-red-500 transition"
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        )}

        {/* ── ADVANCED ── */}
        {activeTab === 'Advanced' && (
          <div className="space-y-4">

            {RAG_SECTIONS.map(section => (
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
                    const isDefault = DEFAULT_TECHS.has(tech.id)
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

                {/* Synthesis: temperature + XAI note */}
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
                    <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
                      <p className="text-xs font-semibold text-blue-700 mb-0.5">XAI — Explainable RAG</p>
                      <p className="text-xs text-blue-600 leading-relaxed">Adds citation tracking and hallucination detection per answer. Enable it per evaluation run in the Evaluation tab.</p>
                    </div>
                  </div>
                )}

              </div>
            ))}

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
        )}

        {/* ── EVALUATION ── */}
        {activeTab === 'Evaluation' && (
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

                <div className="flex items-center gap-2">
                  <input
                    id="eval-xai-checkbox"
                    type="checkbox"
                    checked={evalXai}
                    onChange={e => setEvalXai(e.target.checked)}
                    className="w-4 h-4 accent-orange-400"
                  />
                  <label htmlFor="eval-xai-checkbox" className="text-sm text-gray-600">
                    XAI mode — check citations and detect hallucinations (slower, more LLM calls per question)
                  </label>
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
                              {r.progress.phase === 'indexing'
                                ? 'Indexing documents...'
                                : `Step ${r.progress.step}/${r.progress.total} — question ${r.progress.question_num}/${r.progress.n_questions}, run ${r.progress.exec_num}/${r.progress.n_exec}: "${r.progress.question}"`}
                            </p>
                          )}
                        </button>
                        <div className="flex items-center gap-3">
                          {r.status === 'running' && <span className="text-xs text-orange-500 bg-orange-50 px-2 py-1 rounded-full animate-pulse">Running...</span>}
                          {r.status === 'error' && <span className="text-xs text-red-400 bg-red-50 px-2 py-1 rounded-full">Error</span>}
                          {r.status === 'done' && r.global_results && (() => {
                            const rouge1 = r.global_results.avg_rouge1
                            const colorClass = rouge1 != null
                              ? rouge1 >= 0.6 ? 'text-green-600 bg-green-50'
                                : rouge1 >= 0.4 ? 'text-orange-500 bg-orange-50'
                                : 'text-red-500 bg-red-50'
                              : 'text-green-600 bg-green-50'
                            const label = rouge1 != null
                              ? `Quality ${Math.round(rouge1 * 100)}%`
                              : `Score ${r.global_results.score.mean}`
                            return <span className={`text-xs px-2 py-1 rounded-full ${colorClass}`}>{label}</span>
                          })()}
                          <button
                            onClick={() => handleDeleteRun(r._id)}
                            className="text-xs text-red-400 hover:text-red-500 transition"
                          >
                            Delete
                          </button>
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
        )}

      </div>
    </div>
  )
}