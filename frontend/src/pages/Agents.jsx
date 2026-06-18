// src/pages/Agents.jsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Agents() {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [showForm, setShowForm] = useState(false)

  const { token, email, logout } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    fetchAgents()
  }, [])

  const fetchAgents = async () => {
    setLoading(true)
    const res = await fetch('/api/agents', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = await res.json()
    setAgents(data)
    setLoading(false)
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!newName.trim()) return
    setCreating(true)

    const res = await fetch('/api/agents', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ name: newName.trim() })
    })

    const data = await res.json()
    setCreating(false)
    if (!res.ok) return
    setNewName('')
    setShowForm(false)
    navigate(`/agents/${data._id}`)
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-white">

      {/* Header */}
      <div className="border-b border-gray-100 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold text-gray-800">My Agents</h1>
          <button
            onClick={() => navigate('/llm-servers')}
            className="text-sm text-orange-400 hover:text-orange-500 transition"
          >
            Manage servers
          </button>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">{email}</span>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-400 hover:text-gray-600 transition"
          >
            Sign out
          </button>
        </div>
      </div>

      {/* Contenido */}
      <div className="max-w-3xl mx-auto px-8 py-10">

        {/* Botón crear */}
        <div className="flex items-center justify-between mb-8">
          <p className="text-sm text-gray-400">
            {agents.length === 0 ? 'No agents yet' : `${agents.length} agent${agents.length > 1 ? 's' : ''}`}
          </p>
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition"
          >
            + New agent
          </button>
        </div>

        {/* Formulario crear agente */}
        {showForm && (
          <form onSubmit={handleCreate} className="mb-6 flex gap-3">
            <input
              autoFocus
              type="text"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="Agent name..."
              className="flex-1 border border-gray-200 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-300"
            />
            <button
              type="submit"
              disabled={creating}
              className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition disabled:opacity-50"
            >
              {creating ? 'Creating...' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="text-sm text-gray-400 hover:text-gray-600 px-3 py-2 transition"
            >
              Cancel
            </button>
          </form>
        )}

        {/* Lista de agentes */}
        {loading ? (
          <p className="text-sm text-gray-400">Loading...</p>
        ) : agents.length === 0 ? (
          <div className="text-center py-20 text-gray-300">
            <p className="text-5xl mb-4">🤖</p>
            <p className="text-sm">Create your first agent to get started</p>
          </div>
        ) : (
          <div className="space-y-3">
            {agents.map(agent => (
              <div
                key={agent._id}
                onClick={() => navigate(`/agents/${agent._id}`)}
                className="border border-gray-100 rounded-xl px-6 py-4 cursor-pointer hover:border-orange-200 hover:bg-orange-50 transition group"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-800 group-hover:text-orange-500 transition">
                      {agent.name}
                    </p>
                    {agent.description && (
                      <p className="text-xs text-gray-400 mt-0.5">{agent.description}</p>
                    )}
                  </div>
                  <div className="text-xs text-gray-300 flex items-center gap-3">
                    <span>{agent.documents?.length || 0} doc{agent.documents?.length !== 1 ? 's' : ''}</span>
                    <span className="text-gray-200">→</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
