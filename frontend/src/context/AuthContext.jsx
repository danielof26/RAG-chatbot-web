import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [email, setEmail] = useState(localStorage.getItem('email'))

  const login = (token, email) => {
    localStorage.setItem('token', token)
    localStorage.setItem('email', email)
    setToken(token)
    setEmail(email)
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('email')
    setToken(null)
    setEmail(null)
  }

  return (
    <AuthContext.Provider value={{ token, email, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
