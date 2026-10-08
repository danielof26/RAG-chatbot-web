import { useMemo } from 'react'
import { useAuth } from '../context/AuthContext'
import { createApi } from './apiClient'

export function useApi() {
  const { token, logout } = useAuth()
  // Clearing the token makes PrivateRoute send the user back to the login page
  return useMemo(() => createApi(token, logout), [token, logout])
}
