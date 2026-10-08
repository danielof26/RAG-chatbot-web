import { useState, useEffect, useRef } from 'react'

export default function DocumentsTab({ agent, id, api, navigate, llmServers, onDocumentsChange }) {
  const [embedServerId, setEmbedServerId] = useState(agent.embed_server_id || '')
  const [embedModel, setEmbedModel] = useState(agent.embed_model || '')
  const [availableEmbedModels, setAvailableEmbedModels] = useState([])
  const [loadingEmbedModels, setLoadingEmbedModels] = useState(false)
  const [savingEmbed, setSavingEmbed] = useState(false)
  const [embedSaveMsg, setEmbedSaveMsg] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [indexingMsg, setIndexingMsg] = useState('')
  const fileRef = useRef()

  const fetchDocuments = async () => {
    const res = await api.get(`/api/agents/${id}/documents`)
    if (!res.ok) return
    const documents = await res.json()
    onDocumentsChange(documents)
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    setUploadMsg('')
    const form = new FormData()
    form.append('file', file)
    const res = await api.upload(`/api/agents/${id}/documents`, form)
    const data = await res.json()
    setUploading(false)
    setUploadMsg(res.ok ? data.message : data.error)
    if (res.ok) await fetchDocuments()
    fileRef.current.value = ''
  }

  const handleDeleteDocument = async (filename) => {
    if (!globalThis.confirm(`Delete "${filename}"? This cannot be undone.`)) return
    const res = await api.delete(`/api/agents/${id}/documents/${encodeURIComponent(filename)}`)
    if (res.ok) await fetchDocuments()
  }

  const handleIndex = async (filename) => {
    setIndexingMsg('')
    const res = await api.post(`/api/agents/${id}/documents/${encodeURIComponent(filename)}/index`)
    const data = await res.json()
    setIndexingMsg(res.ok ? data.message : data.error)
    if (res.ok) await fetchDocuments()
  }

  const handleSaveEmbedSettings = async () => {
    setSavingEmbed(true)
    setEmbedSaveMsg('')
    const res = await api.put(`/api/agents/${id}`, {
        embed_server_id: embedServerId || null,
        embed_model: embedModel
      })
    setSavingEmbed(false)
    setEmbedSaveMsg(res.ok ? 'Saved!' : 'Error saving')
    if (res.ok) setTimeout(() => setEmbedSaveMsg(''), 2000)
  }

  // Cuando cambia el servidor de embeddings, carga sus modelos
  useEffect(() => {
    if (!embedServerId) { setAvailableEmbedModels([]); return }
    const load = async () => {
      setLoadingEmbedModels(true)
      const res = await api.get(`/api/llm-servers/${embedServerId}/models`)
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

  return (
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
  )
}
