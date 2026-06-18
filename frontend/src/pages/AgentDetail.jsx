// src/pages/AgentDetail.jsx
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const TABS = ['Settings', 'Documents', 'Chat', 'API']

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

  // API Keys
  const [apiKeyRequired, setApiKeyRequired] = useState(false)
  const [apiKeys, setApiKeys] = useState([])
  const [newKeyName, setNewKeyName] = useState('')
  const [createdKey, setCreatedKey] = useState(null)
  const [savingApi, setSavingApi] = useState(false)

  // Documents
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [indexingMsg, setIndexingMsg] = useState('')

  // Chat
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  useEffect(() => { fetchAgent() }, [id])
  useEffect(() => { fetchLlmServers() }, [])
  useEffect(() => { if (activeTab === 'API') fetchApiKeys() }, [activeTab])

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
        embed_server_id: embedServerId || null,
        embed_model: embedModel,
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

  const handleSaveApiSettings = async () => {
    setSavingApi(true)
    await fetch(`/api/agents/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ api_key_required: apiKeyRequired })
    })
    setSavingApi(false)
  }

  const handleChat = async (e) => {
    e.preventDefault()
    if (!question.trim()) return
    setChatLoading(true)
    setAnswer('')
    const res = await fetch(`/api/agents/${id}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ question })
    })
    const data = await res.json()
    setChatLoading(false)
    setAnswer(res.ok ? data.answer : data.error)
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

            {/* Embedding Server selector */}
            <div>
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
              <select
                id="embed-server-select"
                value={embedServerId}
                onChange={e => { setEmbedServerId(e.target.value); setEmbedModel('') }}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 bg-white"
              >
                <option value="">— Select an embedding server (required) —</option>
                {llmServers.filter(s => s.type === 'ollama').map(s => (
                  <option key={s._id} value={s._id}>{s.name}</option>
                ))}
              </select>
            </div>

            {/* Embedding Model selector */}
            {embedServerId && (
              <div>
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
            <form onSubmit={handleChat} className="flex gap-3 mb-6">
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

            {chatLoading && (
              <p className="text-sm text-gray-400 animate-pulse">Thinking...</p>
            )}

            {answer && (
              <div className="bg-gray-50 border border-gray-100 rounded-xl px-6 py-4">
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Answer</p>
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{answer}</p>
              </div>
            )}
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

            {/* Documentación del endpoint */}
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Endpoint</p>
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

      </div>
    </div>
  )
}