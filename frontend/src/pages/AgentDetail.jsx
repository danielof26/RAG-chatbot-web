// src/pages/AgentDetail.jsx
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const TABS = ['Settings', 'Documents', 'Chat', 'API', 'Advanced', 'Evaluation']

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
  const [retrievalMode, setRetrievalMode] = useState('naive')
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
    setRetrievalMode(data.rag_config?.retrieval_mode ?? 'naive')
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
          retrieval_mode: retrievalMode
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
          <div className="space-y-5">
            <p className="text-sm text-gray-400">
              Control how this agent retrieves information from its documents. Changes to chunk
              size/overlap only affect documents indexed (or re-indexed) after saving.
            </p>

            <div>
              <label htmlFor="top-k-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Top K (chunks retrieved per question)
              </label>
              <input
                id="top-k-input"
                type="number"
                min="1"
                max="50"
                value={topK}
                onChange={e => setTopK(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
              <p className="text-xs text-gray-400 mt-1">How many document chunks are fed to the LLM as context for each question.</p>
            </div>

            <div>
              <label htmlFor="chunk-size-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Chunk size
              </label>
              <input
                id="chunk-size-input"
                type="number"
                min="50"
                max="8000"
                value={chunkSize}
                onChange={e => setChunkSize(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
              <p className="text-xs text-gray-400 mt-1">Size (in tokens) of each piece a document is split into when indexed.</p>
            </div>

            <div>
              <label htmlFor="chunk-overlap-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Chunk overlap
              </label>
              <input
                id="chunk-overlap-input"
                type="number"
                min="0"
                max="4000"
                value={chunkOverlap}
                onChange={e => setChunkOverlap(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
              <p className="text-xs text-gray-400 mt-1">How many tokens consecutive chunks share, to avoid cutting context at the boundary.</p>
            </div>

            <div>
              <label htmlFor="temperature-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Temperature
              </label>
              <input
                id="temperature-input"
                type="number"
                min="0"
                max="2"
                step="0.1"
                value={temperature}
                onChange={e => setTemperature(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
              <p className="text-xs text-gray-400 mt-1">
                How much randomness the LLM uses when writing the answer. Lower (e.g. 0) gives
                consistent, fact-focused answers; higher gives more varied, creative ones.
              </p>
            </div>

            <div>
              <label htmlFor="retrieval-mode-input" className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Retrieval mode
              </label>
              <select
                id="retrieval-mode-input"
                value={retrievalMode}
                onChange={e => setRetrievalMode(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              >
                <option value="naive">Naive — retrieve by the question directly</option>
                <option value="hyde_answer">HyDE Answer — retrieve by a hypothetical answer</option>
                <option value="hyde_combined">HyDE Combined — retrieve by question + hypothetical answer</option>
              </select>
              <p className="text-xs text-gray-400 mt-1">
                HyDE modes first ask the LLM to generate a hypothetical answer, then use it to find more relevant document chunks.
              </p>
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
                        <p className="text-xs text-gray-400 mt-0.5">
                          top_k={s.rag_config?.similarity_top_k} · chunk={s.rag_config?.chunk_size}/{s.rag_config?.chunk_overlap} · temp={s.rag_config?.temperature} · {s.llm_model || 'default model'}
                        </p>
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
                            {r.num_questions} questions · {r.n_exec}x · {r.xai ? 'XAI' : 'naive'} · {new Date(r.created_at).toLocaleString()}
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
                          {r.status === 'done' && r.global_results && (
                            <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
                              Score {r.global_results.score.mean}
                            </span>
                          )}
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
                          {r.status === 'done' && expandedRunDetail.results && (
                            <>
                              <div className="text-xs text-gray-600 grid grid-cols-2 gap-2">
                                <p>Mean score: <b>{expandedRunDetail.results.global.score.mean}</b> (min {expandedRunDetail.results.global.score.min}, max {expandedRunDetail.results.global.score.max})</p>
                                {expandedRunDetail.results.global.avg_rouge1 != null && (
                                  <p>ROUGE-1/2/L: {expandedRunDetail.results.global.avg_rouge1} / {expandedRunDetail.results.global.avg_rouge2} / {expandedRunDetail.results.global.avg_rougeL}</p>
                                )}
                                {r.xai && (
                                  <p>Avg. hallucinations: {expandedRunDetail.results.global.avg_hallucinations}</p>
                                )}
                                <p>Time: {expandedRunDetail.results.global.time_seconds}s</p>
                              </div>
                              <div className="space-y-2">
                                {expandedRunDetail.results.per_question.map((pq) => (
                                  <div key={pq.question} className="bg-white border border-gray-100 rounded-lg px-3 py-2">
                                    <p className="text-xs font-medium text-gray-700">{pq.question}</p>
                                    <p className="text-xs text-gray-400 mt-1">{pq.last_answer}</p>
                                    <p className="text-xs text-gray-500 mt-1">
                                      Score: {pq.score.mean} {pq.rouge1_mean != null && `· ROUGE-1 ${pq.rouge1_mean}`} {r.xai && `· Hallucinations ${pq.hallucinations_mean}`}
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