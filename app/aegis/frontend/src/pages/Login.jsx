import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useBehaviorCapture } from '../hooks/useBehaviorCapture'

export default function Login({ onLogin }) {
  const [msisdn, setMsisdn] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [tempSessionId] = useState(() => crypto.randomUUID())
  const capture = useBehaviorCapture(tempSessionId)
  const navigate = useNavigate()

  useEffect(() => { capture.trackNav('LOGIN') }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const res = await fetch('/bank/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ msisdn, pin, device_fingerprint: navigator.userAgent })
      })
      if (!res.ok) {
        const body = await res.json()
        setError(body.detail || 'We couldn\u2019t sign you in. Check your details and try again.')
        return
      }
      const data = await res.json()
      onLogin(data)
      navigate('/bank/home')
    } catch {
      setError('Could not reach the server. Is the backend running?')
    }
  }

  return (
    <div className="theme-bank" style={{ minHeight: '100vh', display: 'flex' }}>
      <div style={{
        flex: '0 0 42%', background: 'var(--bank-navy-900)', color: '#fff',
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: 48
      }}>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 22 }}>SEES HACK Bank</div>
        <div>
          <div style={{ width: 40, height: 4, background: 'var(--bank-orange)', marginBottom: 20 }} />
          <p style={{ fontSize: 20, lineHeight: 1.5, maxWidth: 340, fontFamily: 'var(--font-display)', fontWeight: 600 }}>
            Banking that knows the difference between you and someone pretending to be you.
          </p>
        </div>
        <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)' }}>Demo environment &#8226; simulated data</div>
      </div>

      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <form onSubmit={handleSubmit} style={{ width: 360 }}>
          <h1 style={{ fontSize: 26, marginBottom: 6, color: 'var(--bank-ink)' }}>Welcome back</h1>
          <p style={{ color: 'var(--bank-ink-dim)', fontSize: 14, marginBottom: 32 }}>Sign in to manage your account</p>

          <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--bank-ink)' }}>Phone number</label>
          <input
            value={msisdn} onChange={(e) => setMsisdn(e.target.value)}
            onKeyDown={capture.onKeyDown} onKeyUp={capture.onKeyUp} onPaste={capture.onPaste} onMouseMove={capture.onMouseMove}
            placeholder="080XXXXXXXX" style={inputStyle}
          />

          <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--bank-ink)', marginTop: 18, display: 'block' }}>PIN</label>
          <input
            type="password" value={pin} onChange={(e) => setPin(e.target.value)}
            onKeyDown={capture.onKeyDown} onKeyUp={capture.onKeyUp} onPaste={capture.onPaste}
            placeholder="••••" style={inputStyle}
          />

          {error && <p style={{ color: 'var(--verdict-high)', fontSize: 13, marginTop: 14 }}>{error}</p>}

          <button type="submit" style={{
            width: '100%', marginTop: 28, padding: 14, background: 'var(--bank-orange)',
            color: '#fff', border: 'none', borderRadius: 8, fontSize: 15, fontWeight: 600, cursor: 'pointer'
          }}>
            Sign in
          </button>
        </form>
      </div>
    </div>
  )
}

const inputStyle = { width: '100%', padding: '12px 14px', marginTop: 8, borderRadius: 8, border: '1px solid var(--bank-border)', fontSize: 15, background: '#fff', color: 'var(--bank-ink)' }
