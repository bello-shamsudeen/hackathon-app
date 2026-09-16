import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Landing from './pages/Landing'
import Register from './pages/Register'
import Login from './pages/Login'
import Home from './pages/Home'
import SendMoney from './pages/SendMoney'
import TransactionHistory from './pages/TransactionHistory'
import Profile from './pages/Profile'
import UssdSimulator from './pages/UssdSimulator'

function OpsPlaceholder() {
  return (
    <div className="theme-ops" style={{ minHeight: '100vh', padding: 48 }}>
      <h1>Aegis Operations Console</h1>
      <p style={{ color: 'var(--ops-text-dim)' }}>Coming in Division 9B.</p>
    </div>
  )
}
function TourPlaceholder() {
  return (
    <div className="theme-ops" style={{ minHeight: '100vh', padding: 48 }}>
      <h1>Guided Tour</h1>
      <p style={{ color: 'var(--ops-text-dim)' }}>Coming in Division 9C.</p>
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState(null)
  const [showColdStartHint, setShowColdStartHint] = useState(false)

  const handleLogin = (data) => {
    setSession(data)
    if (data.is_freshly_registered) setShowColdStartHint(true)
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing onLogin={handleLogin} />} />
        <Route path="/register" element={<Register onRegistered={handleLogin} />} />
        <Route path="/bank" element={<Login onLogin={handleLogin} />} />
        <Route path="/bank/home" element={
          <Home session={session} showColdStartHint={showColdStartHint} dismissColdStartHint={() => setShowColdStartHint(false)} />
        } />
        <Route path="/bank/send" element={<SendMoney session={session} />} />
        <Route path="/bank/history" element={<TransactionHistory session={session} />} />
        <Route path="/bank/profile" element={<Profile session={session} />} />
        <Route path="/bank/ussd" element={<UssdSimulator />} />
        <Route path="/ops" element={<OpsPlaceholder />} />
        <Route path="/tour" element={<TourPlaceholder />} />
      </Routes>
    </BrowserRouter>
  )
}
