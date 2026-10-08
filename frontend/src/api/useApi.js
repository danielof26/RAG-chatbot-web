import { useMemo } from 'react'
import { useAuth } from '../context/AuthContext'
import { createApi } from './apiClient'

export function useApi() {
  const { token } = useAuth()
  return useMemo(() => createApi(token), [token])
}
