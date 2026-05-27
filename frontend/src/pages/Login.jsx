import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const endpoint = isRegister ? '/api/register' : '/api/login'

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.error || 'Something went wrong')
        return
      }

      if (isRegister) {
        setIsRegister(false)
        setError('')
        setEmail('')
        setPassword('')
        alert('Account created. Please sign in.')
      } else {
        login(data.token, data.email)
        navigate('/agents')
      }
    } catch {
      setError('Connection error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-white flex items-center justify-center relative overflow-hidden">

      {/* Patrón de puntos */}
      <div className="absolute inset-0 opacity-[0.15]" style={{
        backgroundImage: 'radial-gradient(circle, #f97316 1.5px, transparent 1.5px)',
        backgroundSize: '28px 28px'
      }} />

      {/* Rectángulos inclinados detrás del card */}
      <div className="absolute w-[430px] h-[530px] bg-orange-100 border-2 border-orange-200 rounded-3xl rotate-6 shadow-md" />
      <div className="absolute w-[430px] h-[530px] bg-orange-50 border-2 border-orange-100 rounded-3xl -rotate-3 shadow-sm" />

      {/* Card */}
      <div className="relative z-10 bg-white/80 backdrop-blur-sm border border-gray-100 shadow-sm p-8 rounded-2xl w-full max-w-md">

        <h1 className="text-2xl font-semibold text-gray-800 mb-1 text-center">
          {isRegister ? 'Create account' : 'Welcome back'}
        </h1>
        <p className="text-gray-400 text-sm text-center mb-7">
          {isRegister ? 'Fill in your details to get started' : 'Sign in to continue'}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1 uppercase tracking-wide">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent transition"
              placeholder="you@email.com"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1 uppercase tracking-wide">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-orange-300 focus:border-transparent transition"
              placeholder="At least 6 characters"
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-orange-400 hover:bg-orange-500 text-white font-medium py-2.5 rounded-lg transition disabled:opacity-50 mt-2"
          >
            {loading ? 'Loading...' : isRegister ? 'Create account' : 'Sign in'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-400 mt-6">
          {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
          <button
            onClick={() => { setIsRegister(!isRegister); setError('') }}
            className="text-orange-400 hover:text-orange-500 font-medium transition"
          >
            {isRegister ? 'Sign in' : 'Sign up'}
          </button>
        </p>

      </div>
    </div>
  )
}
