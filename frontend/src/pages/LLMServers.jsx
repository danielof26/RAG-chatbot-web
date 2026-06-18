import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function LLMServers() {
  const { token } = useAuth()
  const navigate = useNavigate()

  const [servers, setServers] = useState([])
  const [loading, setLoading] = useState(true)

  const [type, setType] = useState('ollama')
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => { fetchServers() }, [])

  const handleTypeChange = (newType) => {
    setType(newType)
    setBaseUrl('')
    setApiKey('')
  }

  const fetchServers = async () => {
    setLoading(true)
    const res = await fetch('/api/llm-servers', {
      headers: { Authorization: `Bearer ${token}` }
    })
    const data = await res.json()
    setServers(res.ok ? data : [])
    setLoading(false)
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMsg('')

    const body = { name, type }
    if (type === 'ollama') body.base_url = baseUrl
    else if (type === 'openai') { body.base_url = baseUrl; body.api_key = apiKey }
    else body.api_key = apiKey

    const res = await fetch('/api/llm-servers', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(body)
    })
    const data = await res.json()
    setSaving(false)

    if (res.ok) {
      setMsg('Server added!')
      setName('')
      setBaseUrl('')
      setApiKey('')
      await fetchServers()
    } else {
      setMsg(data.error || 'Error adding server')
    }
  }

  const handleDelete = async (id) => {
    if (!globalThis.confirm('Delete this server?')) return
    await fetch(`/api/llm-servers/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    })
    await fetchServers()
  }

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
        <h1 className="text-lg font-semibold text-gray-800">LLM Servers</h1>
      </div>

      <div className="max-w-2xl mx-auto px-8 py-10 space-y-10">

        {/* Formulario añadir */}
        <div>
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4">Add server</h2>
          <form onSubmit={handleAdd} className="space-y-4">

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => handleTypeChange('ollama')}
                className={`flex-1 py-2 text-sm font-medium rounded-lg border transition ${
                  type === 'ollama'
                    ? 'border-orange-400 text-orange-500 bg-orange-50'
                    : 'border-gray-200 text-gray-400'
                }`}
              >
                Ollama
              </button>
              <button
                type="button"
                onClick={() => handleTypeChange('gemini')}
                className={`flex-1 py-2 text-sm font-medium rounded-lg border transition ${
                  type === 'gemini'
                    ? 'border-orange-400 text-orange-500 bg-orange-50'
                    : 'border-gray-200 text-gray-400'
                }`}
              >
                Gemini
              </button>
              <button
                type="button"
                onClick={() => handleTypeChange('openai')}
                className={`flex-1 py-2 text-sm font-medium rounded-lg border transition ${
                  type === 'openai'
                    ? 'border-orange-400 text-orange-500 bg-orange-50'
                    : 'border-gray-200 text-gray-400'
                }`}
              >
                OpenAI
              </button>
            </div>

            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Name (e.g. My Ollama)"
              required
              className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
            />

            {type === 'ollama' && (
              <input
                value={baseUrl}
                onChange={e => setBaseUrl(e.target.value)}
                placeholder="Server URL (e.g. http://localhost:11434)"
                required
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            )}

            {type === 'gemini' && (
              <input
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="Gemini API Key"
                type="password"
                required
                className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            )}

            {type === 'openai' && (
              <>
                <input
                  value={baseUrl}
                  onChange={e => setBaseUrl(e.target.value)}
                  placeholder="API base URL (e.g. http://host:4000)"
                  required
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                />
                <input
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  placeholder="API Key"
                  type="password"
                  required
                  className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
                />
              </>
            )}

            <div className="flex items-center justify-between">
              {msg && <span className="text-sm text-gray-400">{msg}</span>}
              <button
                type="submit"
                disabled={saving}
                className="ml-auto bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-5 py-2 rounded-lg transition disabled:opacity-50"
              >
                {saving ? 'Adding...' : 'Add server'}
              </button>
            </div>
          </form>
        </div>

        {/* Lista de servidores */}
        <div>
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4">My servers</h2>

          {loading ? (
            <p className="text-sm text-gray-300">Loading...</p>
          ) : servers.length === 0 ? (
            <p className="text-sm text-gray-300">No servers configured yet.</p>
          ) : (
            <div className="space-y-2">
              {servers.map(s => (
                <div key={s._id} className="flex items-center justify-between border border-gray-100 rounded-lg px-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-gray-700">{s.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {s.type === 'ollama' && s.base_url}
                      {s.type === 'gemini' && `Gemini · ${s.api_key}`}
                      {s.type === 'openai' && `${s.base_url} · ${s.api_key}`}
                    </p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full mr-3 ${
                    s.type === 'ollama' ? 'bg-blue-50 text-blue-500' :
                    s.type === 'gemini' ? 'bg-purple-50 text-purple-500' :
                    'bg-green-50 text-green-600'
                  }`}>
                    {s.type}
                  </span>
                  <button
                    onClick={() => handleDelete(s._id)}
                    className="text-sm text-red-400 hover:text-red-500 transition"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}