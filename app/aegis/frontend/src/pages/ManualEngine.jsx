import { useState } from 'react'

const ACTION_STYLE = {
  allow: { color: '#1B8A5A', bg: 'rgba(27,138,90,0.12)', label: 'ALLOW' },
  step_up: { color: '#B07C00', bg: 'rgba(216,150,20,0.15)', label: 'STEP-UP / CHALLENGE' },
  block: { color: '#D64550', bg: 'rgba(214,69,80,0.12)', label: 'BLOCK' },
}
const inputStyle = {
  width: '100%', padding: '12px 14px', borderRadius: 8, border: '1px solid var(--ops-border)',
  background: 'transparent', color: '#fff', fontSize: 15, marginBottom: 16, boxSizing: 'border-box',
}

export default function ManualEngine({ session }) {
  const [account, setAccount] = useState('')
  const [amount, setAmount] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const send = async () => {
    if (!account || !amount) return
    if (!session || !session.session_id) {
      setError('No active session. Log in first via "Try the SEES HACKS demo account" on the landing page.')
      return
    }
    setBusy(true); setError(null); setResult(null)
    try {
      const res = await fetch('/bank/transfer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: session.session_id,
          beneficiary_account: account,
          amount: Number(amount),
        }),
      })
      if (!res.ok) throw new Error('HTTP ' + res.status)
      const data = await res.json()
      setResult(data.detection || { error: 'Transfer recorded, but no detection result was returned.' })
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }

  const s = result && result.action ? ACTION_STYLE[result.action] || ACTION_STYLE.allow : null
  const gated = result && result.action === 'block'

  return (
    <div className="theme-ops" style={{ width: '100%', maxWidth: 640, margin: '0 auto', padding: '48px 20px' }}>
      <h1 style={{ fontSize: 24, marginBottom: 6, color: '#fff' }}>Transfer Session</h1>
      <p style={{ color: 'rgba(255,255,255,0.65)', fontSize: 14, lineHeight: 1.6, marginBottom: 24 }}>
        Every transfer is scored by the detection engine before it settles. Flags appear here first.
      </p>

      <div style={{ background: 'var(--ops-panel)', border: '1px solid var(--ops-border)', borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <label style={{ display: 'block', fontSize: 13, color: 'rgba(255,255,255,0.6)', marginBottom: 6 }}>Beneficiary account number</label>
        <input value={account} onChange={e => setAccount(e.target.value.replace(/\D/g, '').slice(0, 10))}
          placeholder="e.g. 0123456789" inputMode="numeric" style={inputStyle} />

        <label style={{ display: 'block', fontSize: 13, color: 'rgba(255,255,255,0.6)', marginBottom: 6 }}>Amount (NGN)</label>
        <input type="number" min="0" value={amount} onChange={e => setAmount(e.target.value)}
          placeholder="e.g. 250000" style={inputStyle} />

        <button onClick={send} disabled={busy || !account || !amount}
          style={{ width: '100%', padding: '13px 0', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 15, fontWeight: 700, background: 'var(--ops-accent)', color: '#04201D', opacity: (busy || !account || !amount) ? 0.6 : 1 }}>
          {busy ? 'Scoring transfer...' : 'Send'}
        </button>
      </div>

      {error && <div style={{ color: '#D64550', fontSize: 13, marginBottom: 16 }}>{error}</div>}

      {result && (
        <div style={{ background: 'var(--ops-panel)', border: '1px solid var(--ops-border)', borderRadius: 12, padding: 24, fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          {result.error ? (
            <div style={{ color: '#D64550' }}>detection error: {result.error}</div>
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <span style={{ color: 'rgba(255,255,255,0.55)' }}>scored before settlement</span>
                <span style={{ color: s.color, background: s.bg, padding: '4px 12px', borderRadius: 6, fontWeight: 700 }}>{s.label}</span>
              </div>
              <div style={{ marginBottom: 6, color: 'rgba(255,255,255,0.85)' }}>risk_score: <span style={{ color: '#fff' }}>{result.risk_score}</span> (tier: {result.tier})</div>
              {result.velocity && <div style={{ marginBottom: 6, color: 'rgba(255,255,255,0.85)' }}>transfers/hr: {result.velocity.transfers_per_hour ?? 0} | logins/min: {result.velocity.login_attempts_per_min ?? 0}</div>}
              <div style={{ marginTop: 12, color: '#fff' }}>&ldquo;{result.message}&rdquo;</div>
              <div style={{ marginTop: 14, color: gated ? '#D64550' : '#1B8A5A', fontWeight: 700 }}>
                {gated ? 'Transfer held - flag raised before the send completed.' : 'Transfer cleared - no blocking flag.'}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}