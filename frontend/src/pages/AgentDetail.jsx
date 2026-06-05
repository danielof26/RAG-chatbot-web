// src/pages/AgentDetail.jsx
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const TABS = ['Settings', 'Documents', 'Chat']

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
  const [llmModel, setLlmModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')

  // Documents
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [indexingMsg, setIndexingMsg] = useState('')

  // Chat
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  useEffect(() => { fetchAgent() }, [id])

  // Auto-refresh mientras haya documentos indexando
  useEffect(() => {
    const hasIndexing = agent?.documents?.some(d => d.status === 'indexing')
    if (!hasIndexing) return
    const interval = setInterval(fetchAgent, 3000)
    return () => clearInterval(interval)
  }, [agent])

  const fetchAgent = async () => {
    setLoading(true)
    const res = await fetch(`/api/agents/${id}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!res.ok) {
      navigate('/agents')
      return
    }
    const data = await res.json()
    setAgent(data)
    setName(data.name || '')
    setDescription(data.description || '')
    setPrompt(data.prompt || '')
    setLlmModel(data.llm_model || '')
    setLoading(false)
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveMsg('')
    const res = await fetch(`/api/agents/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ name, description, prompt, llm_model: llmModel })
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
    if (!window.confirm('Delete this agent? This cannot be undone.')) return
    await fetch(`/api/agents/${id}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
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
      headers: { 'Authorization': `Bearer ${token}` },
      body: form
    })
    const data = await res.json()
    setUploading(false)
    setUploadMsg(res.ok ? data.message : data.error)
    if (res.ok) await fetchAgent()
    fileRef.current.value = ''
  }

  const handleIndex = async (filename) => {
    setIndexingMsg('')
    const res = await fetch(`/api/agents/${id}/documents/${encodeURIComponent(filename)}/index`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = await res.json()
    setIndexingMsg(res.ok ? data.message : data.error)
    if (res.ok) await fetchAgent()
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
        'Authorization': `Bearer ${token}`
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
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Name</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Description</label>
              <input
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="What does this agent do?"
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">System prompt</label>
              <textarea
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                rows={5}
                placeholder="You are an assistant that..."
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300 resize-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">LLM Model</label>
              <input
                value={llmModel}
                onChange={e => setLlmModel(e.target.value)}
                placeholder="e.g. llama3.2:3b"
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </div>

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
                {agent.documents?.map((doc, i) => (
                  <div key={i} className="flex items-center justify-between border border-gray-100 rounded-lg px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span className="text-gray-300">📄</span>
                      <span className="text-sm text-gray-600">{doc.filename}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      {doc.status === 'pending'   && <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">Pending</span>}
                      {doc.status === 'indexing'  && <span className="text-xs text-orange-500 bg-orange-50 px-2 py-1 rounded-full animate-pulse">Indexing...</span>}
                      {doc.status === 'indexed'   && <span className="text-xs text-green-500 bg-green-50 px-2 py-1 rounded-full">Indexed</span>}
                      {doc.status === 'error'     && <span className="text-xs text-red-400 bg-red-50 px-2 py-1 rounded-full">Error</span>}
                      {(doc.status === 'pending' || doc.status === 'error') && (
                        <button
                          onClick={() => handleIndex(doc.filename)}
                          className="text-xs bg-orange-400 hover:bg-orange-500 text-white px-3 py-1 rounded-lg transition"
                        >
                          Index
                        </button>
                      )}
                    </div>
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

      </div>
    </div>
  )
}
