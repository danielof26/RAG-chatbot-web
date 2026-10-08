import { useState, useEffect } from 'react'

export default function SettingsTab({ agent, id, api, navigate, llmServers, apiKeyRequired }) {
  const [name, setName] = useState(agent.name || '')
  const [description, setDescription] = useState(agent.description || '')
  const [prompt, setPrompt] = useState(agent.prompt || '')
  const [llmServerId, setLlmServerId] = useState(agent.llm_server_id || '')
  const [llmModel, setLlmModel] = useState(agent.llm_model || '')
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [availableModels, setAvailableModels] = useState([])
  const [loadingModels, setLoadingModels] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    setSaveMsg('')
    const res = await api.put(`/api/agents/${id}`, {
        name, description, prompt,
        llm_server_id: llmServerId || null,
        llm_model: llmModel,
        api_key_required: apiKeyRequired
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
    await api.delete(`/api/agents/${id}`)
    navigate('/agents')
  }

  // Cuando cambia el servidor seleccionado, carga sus modelos
  useEffect(() => {
    if (!llmServerId) { setAvailableModels([]); return }
    const load = async () => {
      setLoadingModels(true)
      const res = await api.get(`/api/llm-servers/${llmServerId}/models`)
      const data = await res.json()
      setAvailableModels(res.ok ? data.models : [])
      setLoadingModels(false)
    }
    load()
  }, [llmServerId])

  return (
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
  )
}
