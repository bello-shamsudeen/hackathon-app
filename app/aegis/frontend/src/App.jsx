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
import ManualEngine from './pages/ManualEngine'
import DemoHub from './components/DemoHub'

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
        <Route element={<DemoHub session={session} />}>
          <Route path="/bank/home" element={
            <Home session={session} showColdStartHint={showColdStartHint} dismissColdStartHint={() => setShowColdStartHint(false)} />
          } />
          <Route path="/bank/send" element={<SendMoney session={session} />} />
          <Route path="/bank/history" element={<TransactionHistory session={session} />} />
          <Route path="/bank/profile" element={<Profile session={session} />} />
          <Route path="/bank/ussd" element={<UssdSimulator />} />
          <Route path="/demo/manual" element={<ManualEngine session={session} />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
