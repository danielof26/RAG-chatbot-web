import { useState, useEffect } from 'react'

export default function ApiTab({ id, api, active, apiKeyRequired, setApiKeyRequired }) {
  const [apiKeys, setApiKeys] = useState([])
  const [newKeyName, setNewKeyName] = useState('')
  const [createdKey, setCreatedKey] = useState(null)
  const [savingApi, setSavingApi] = useState(false)

  const fetchApiKeys = async () => {
    const res = await api.get(`/api/agents/${id}/api-keys`)
    if (res.ok) setApiKeys(await res.json())
  }

  const handleCreateKey = async () => {
    const res = await api.post(`/api/agents/${id}/api-keys`, { name: newKeyName.trim() || undefined })
    if (!res.ok) return
    const created = await res.json()
    setCreatedKey(created)
    setNewKeyName('')
    await fetchApiKeys()
  }

  const handleDeleteKey = async (keyId) => {
    if (!globalThis.confirm('Delete this API key? This cannot be undone.')) return
    await api.delete(`/api/agents/${id}/api-keys/${keyId}`)
    await fetchApiKeys()
  }

  const handleSaveApiSettings = async () => {
    setSavingApi(true)
    await api.put(`/api/agents/${id}`, { api_key_required: apiKeyRequired })
    setSavingApi(false)
  }

  useEffect(() => { if (active) fetchApiKeys() }, [active])

  return (
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
  )
}
