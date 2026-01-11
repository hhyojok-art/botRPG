import React, { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function App() {
  const [loading, setLoading] = useState(true)
  const [enabled, setEnabled] = useState(true)
  const [error, setError] = useState(null)

  async function fetchHealth() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/health`)
      const data = await res.json()
      setEnabled(data.bot_enabled)
    } catch (err) {
      setError('Gagal mengambil status')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchHealth() }, [])

  async function setMaintenance(on) {
    setError(null)
    try {
      const path = on ? 'maintenance/on' : 'maintenance/off'
      const res = await fetch(`${API_BASE}/${path}`, { method: 'POST' })
      if (!res.ok) throw new Error('request failed')
      await fetchHealth()
    } catch (err) {
      setError('Gagal mengubah mode maintenance')
    }
  }

  return (
    <div className="container">
      <h1>Bot Dashboard</h1>
      <div className="card">
        <h2>Maintenance</h2>
        {loading ? (
          <p>Memuat status...</p>
        ) : (
          <>
            <p>Status bot: <strong>{enabled ? 'ON' : 'MAINTENANCE'}</strong></p>
            <div className="buttons">
              <button className="btn" onClick={() => setMaintenance(false)}>Turn OFF (enable)</button>
              <button className="btn danger" onClick={() => setMaintenance(true)}>Turn ON (maintenance)</button>
            </div>
          </>
        )}
        {error && <p className="error">{error}</p>}
      </div>
      <div className="card">
        <h2>Actions</h2>
        <button className="btn" onClick={fetchHealth}>Refresh</button>
      </div>
    </div>
  )
}
