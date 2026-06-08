// src/App.jsx
import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Agents from './pages/Agents'
import AgentDetail from './pages/AgentDetail'
import LLMServers from './pages/LLMServers'
import PrivateRoute from './components/PrivateRoute'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route path="/agents" element={
        <PrivateRoute><Agents /></PrivateRoute>
      } />

      <Route path="/agents/:id" element={
        <PrivateRoute><AgentDetail /></PrivateRoute>
      } />

      <Route path="/llm-servers" element={
        <PrivateRoute><LLMServers /></PrivateRoute>
      } />

      {/* Redirige la raíz al login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
