import { useState, useEffect, useRef } from 'react'

export default function ChatTab({ id, api, active }) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = useRef()

  const fetchChatHistory = async () => {
    setLoadingHistory(true)
    const res = await api.get(`/api/agents/${id}/chat/history`)
    if (res.ok) {
      const history = await res.json()
      setMessages(history.map(m => ({ ...m, key: m._id })))
    }
    setLoadingHistory(false)
  }

  const handleClearChat = async () => {
    if (!globalThis.confirm('Clear the whole conversation? This cannot be undone.')) return
    await api.delete(`/api/agents/${id}/chat/history`)
    setMessages([])
  }

  const handleChat = async (e) => {
    e.preventDefault()
    if (!question.trim()) return
    const askedQuestion = question
    setQuestion('')
    setMessages(prev => [...prev, { role: 'user', content: askedQuestion, key: `${Date.now()}-${Math.random().toString(36).slice(2)}` }])
    setChatLoading(true)
    const res = await api.post(`/api/agents/${id}/chat`, { question: askedQuestion })
    const data = await res.json()
    setChatLoading(false)
    setMessages(prev => [...prev, { role: 'assistant', content: res.ok ? data.answer : data.error, key: `${Date.now()}-${Math.random().toString(36).slice(2)}` }])
  }

  useEffect(() => { if (active) fetchChatHistory() }, [active])

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  return (
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
  )
}
