import { useState } from 'react'

/**
 * Division 2B — USSD simulator front-end.
 * Styled loosely like a feature-phone screen, but the important part is
 * underneath: it talks to POST /ussd using the EXACT accumulated-text
 * protocol a real telco aggregator would use. See backend routers/ussd.py.
 */
export default function UssdSimulator() {
  const [sessionId] = useState(() => crypto.randomUUID())
  const [phoneNumber] = useState('08012345678') // demo number; should match a seeded synthetic user
  const [textSteps, setTextSteps] = useState([]) // accumulated key presses this session
  const [screen, setScreen] = useState('Dial *737# to begin')
  const [input, setInput] = useState('')
  const [ended, setEnded] = useState(false)

  const sendToBackend = async (newSteps) => {
    const text = newSteps.join('*')
    const res = await fetch('/ussd', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionId,
        phoneNumber,
        serviceCode: '*737#',
        text
      })
    })
    const body = await res.text()
    if (body.startsWith('END')) {
      setEnded(true)
      setScreen(body.slice(4))
    } else if (body.startsWith('CON')) {
      setScreen(body.slice(4))
    }
  }

  const dial = () => {
    setTextSteps([])
    setEnded(false)
    sendToBackend([])
  }

  const submitStep = () => {
    if (!input) return
    const newSteps = [...textSteps, input]
    setTextSteps(newSteps)
    setInput('')
    sendToBackend(newSteps)
  }

  return (
    <div style={{ maxWidth: 340, margin: '48px auto', padding: '0 20px', fontFamily: 'monospace' }}>
      <div style={{
        background: '#9ead86', color: '#1a1a1a', padding: 20,
        minHeight: 160, whiteSpace: 'pre-wrap', fontSize: 15, lineHeight: 1.5, border: '4px solid #333', borderRadius: 4
      }}>
        {screen}
      </div>

      {!ended ? (
        <div style={{ marginTop: 14, display: 'flex', gap: 8 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            style={{ flex: 1, padding: '10px 12px', fontSize: 15, fontFamily: 'monospace', border: '1px solid #999', borderRadius: 4 }}
            placeholder="press keys..."
          />
          <button onClick={submitStep} style={ussdBtn}>Send</button>
        </div>
      ) : (
        <button style={{ ...ussdBtn, marginTop: 14, width: '100%' }} onClick={dial}>
          Dial again
        </button>
      )}

      {textSteps.length === 0 && !ended && (
        <button style={{ ...ussdBtn, marginTop: 14, width: '100%' }} onClick={dial}>
          Dial *737#
        </button>
      )}

      <p style={{ fontSize: 12, color: '#888', marginTop: 16, lineHeight: 1.5 }}>
        Every step above is a real POST to /ussd using the accumulated-text protocol &mdash;
        this is the same contract a live telco aggregator would use.
      </p>
    </div>
  )
}

const ussdBtn = { padding: '10px 16px', fontSize: 15, fontFamily: 'monospace', border: '1px solid #999', borderRadius: 4, background: '#fff', cursor: 'pointer' }