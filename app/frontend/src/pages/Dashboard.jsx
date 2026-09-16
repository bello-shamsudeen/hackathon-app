import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useBehaviorCapture } from '../hooks/useBehaviorCapture'

export default function Dashboard({ session }) {
  const [balance, setBalance] = useState(null)
  const capture = useBehaviorCapture(session?.session_id)
  const navigate = useNavigate()

  useEffect(() => {
    capture.trackNav('DASHBOARD')
    if (!session) { navigate('/'); return }
    fetch(`/bank/dashboard/${session.session_id}`)
      .then(r => r.json())
      .then(setBalance)
  }, [session])

  if (!session) return null

  return (
    <div style={{ maxWidth: 400, margin: '80px auto', fontFamily: 'sans-serif' }}
         onMouseMove={capture.onMouseMove}>
      <h2>Welcome, {session.full_name}</h2>
      <p style={{ fontSize: 12, color: '#666' }}>(Division 2 — functional only, no styling yet)</p>
      {balance && <p>Balance: {balance.currency} {balance.balance.toLocaleString()}</p>}

      <label style={{ display: 'block', marginTop: 20 }}>
        <input
          type="checkbox"
          onChange={(e) => capture.setCallActive(e.target.checked)}
        /> Simulate: on a phone call right now (demo toggle for Division 5's coaching-detection signal)
      </label>

      <button
        style={{ marginTop: 20, padding: 10, width: '100%' }}
        onClick={() => navigate('/send-money')}
      >
        Send Money
      </button>
    </div>
  )
}
