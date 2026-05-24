import { useState } from 'react'

function App() {
  const [mensaje, setMensaje] = useState('')

  const llamarBackend = async () => {
    const res = await fetch('/api/hello')
    const data = await res.json()
    setMensaje(data.message)
  }

  return (
    <div>
      <h1>RAG Chatbot 🤖</h1>
      <button onClick={llamarBackend}>Llamar al backend</button>
      {mensaje && <p>Respuesta: {mensaje}</p>}
    </div>
  )
}

export default App
