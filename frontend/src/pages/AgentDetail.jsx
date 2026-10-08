// src/pages/AgentDetail.jsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useApi } from '../api/useApi'
import SettingsTab from './agent/SettingsTab'
import DocumentsTab from './agent/DocumentsTab'
import ChatTab from './agent/ChatTab'
import ApiTab from './agent/ApiTab'
import AdvancedTab from './agent/AdvancedTab'
import EvaluationTab from './agent/EvaluationTab'

const TABS = ['Settings', 'Documents', 'Chat', 'API', 'Advanced', 'Evaluation']

export default function AgentDetail() {
  const { id } = useParams()
  const api = useApi()
  const navigate = useNavigate()

  const [agent, setAgent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('Settings')
  const [llmServers, setLlmServers] = useState([])
  const [apiKeyRequired, setApiKeyRequired] = useState(false)
  const [catalog, setCatalog] = useState(null)

  useEffect(() => { fetchAgent() }, [id])
  useEffect(() => { fetchLlmServers() }, [])

  const fetchAgent = async () => {
    const [res, catalogRes] = await Promise.all([api.get(`/api/agents/${id}`), api.get('/api/rag/techniques').catch(() => null)])
    if (!res.ok) { navigate('/agents'); return }
    const data = await res.json()
    setCatalog(catalogRes?.ok ? await catalogRes.json() : null)
    setAgent(data)
    setApiKeyRequired(data.api_key_required || false)
    setLoading(false)
  }

  const fetchLlmServers = async () => {
    const res = await api.get('/api/llm-servers')
    const data = await res.json()
    setLlmServers(res.ok ? data : [])
  }

  // Tabs stay mounted (only hidden) so what you typed and haven't saved survives switching tabs.
  // key={agent._id} remounts them, re-reading their initial values, when the route points to another agent.
  const handleDocumentsChange = (documents) => setAgent(prev => prev && { ...prev, documents })
  const panel = (tab, content) => <div hidden={activeTab !== tab}>{content}</div>

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

        {panel('Settings', <SettingsTab key={agent._id} agent={agent} id={id} api={api} navigate={navigate} llmServers={llmServers} apiKeyRequired={apiKeyRequired} />)}
        {panel('Documents', <DocumentsTab key={agent._id} agent={agent} id={id} api={api} navigate={navigate} llmServers={llmServers} onDocumentsChange={handleDocumentsChange} />)}
        {panel('Chat', <ChatTab key={agent._id} id={id} api={api} active={activeTab === 'Chat'} />)}
        {panel('API', <ApiTab key={agent._id} id={id} api={api} active={activeTab === 'API'} apiKeyRequired={apiKeyRequired} setApiKeyRequired={setApiKeyRequired} />)}
        {panel('Advanced', <AdvancedTab key={agent._id} agent={agent} id={id} api={api} catalog={catalog} />)}
        {panel('Evaluation', <EvaluationTab key={agent._id} id={id} api={api} active={activeTab === 'Evaluation'} />)}

      </div>
    </div>
  )
}
