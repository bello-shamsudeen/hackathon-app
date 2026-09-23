import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import PhoneFrame from '../components/PhoneFrame'
import { useBehaviorCapture } from '../hooks/useBehaviorCapture'

const RECENTS = [
  { name: 'Chidi O.', account: '0123456789' },
  { name: 'Blessing A.', account: '9876543210' },
]

export default function SendMoney({ session }) {
  const [step, setStep] = useState(1) // 1=recipient, 2=amount, 3=review, 4=result
  const [beneficiary, setBeneficiary] = useState('')
  const [amount, setAmount] = useState('')
  const [honeytoken, setHoneytoken] = useState('')
  const [decision, setDecision] = useState(null)
  const [otpHold, setOtpHold] = useState(null) // { transactionId, demoOtp }
  const [otp, setOtp] = useState('')
  const [loading, setLoading] = useState(false)
  const capture = useBehaviorCapture(session?.session_id)
  const navigate = useNavigate()

  useEffect(() => { capture.trackNav('TRANSFER') }, [])

  if (!session) { navigate('/bank'); return null }

  const handleConfirm = async () => {
    setLoading(true)
    const transferRes = await fetch('/bank/transfer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: session.session_id, beneficiary_account: beneficiary,
        amount: parseFloat(amount), confirm_email_address: honeytoken,
      })
    })
    const transferData = await transferRes.json()

    if (transferData.status === 'blocked' && transferData.detection?.action === 'block') {
      window.dispatchEvent(new CustomEvent('aegis:blocked', {
        detail: transferData.blocked_until || transferData.detection?.blocked_until || null,
      }))
    }
    if (transferData.status === 'otp_required') {
      setOtpHold({ transactionId: transferData.transaction_id, demoOtp: transferData.detection?.otp })
      setOtp('')
      setLoading(false)
      setStep(5)
      return
    }
    if (transferData.status === 'blocked') {
      setDecision({
        kind: 'blocked', tier: 'HIGH',
        message: transferData.detection?.message || 'This transfer was declined because your account is temporarily blocked.',
        blockedUntil: transferData.detection?.blocked_until || null,
        explanationSource: 'deterministic',
      })
    } else if (transferData.status === 'insufficient_funds') {
      setDecision({
        kind: 'error', tier: 'MEDIUM',
        message: 'Insufficient funds. Your balance could not cover this transfer.',
        explanationSource: 'deterministic',
      })
    } else if (transferData.status === 'completed') {
      setDecision({ kind: 'success', ...transferData.detection, explanation: transferData.detection?.message, explanationSource: 'deterministic' })
    } else {
      setDecision({ kind: 'error', tier: 'MEDIUM', message: transferData.detection?.message || 'This transfer could not be completed.', explanationSource: 'deterministic' })
    }
    setLoading(false)
    setStep(4)
  }

  const handleVerify = async () => {
    setLoading(true)
    const res = await fetch('/bank/transfer/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: session.session_id, transaction_id: otpHold.transactionId, otp }),
    })
    const data = await res.json()
    setLoading(false)
    if (data.status === 'completed') {
      setDecision({ kind: 'success', tier: 'LOW', message: data.detection?.message || 'Transfer completed.', explanationSource: 'deterministic' })
    } else if (data.status === 'insufficient_funds') {
      setDecision({ kind: 'error', tier: 'MEDIUM', message: data.detection?.message || 'Insufficient funds to complete this transfer.', explanationSource: 'deterministic' })
    } else if (data.status === 'blocked') {
      setDecision({ kind: 'blocked', tier: 'HIGH', message: data.detection?.message || 'Account blocked. This transfer cannot complete until the block lifts.', blockedUntil: data.detection?.blocked_until || null, explanationSource: 'deterministic' })
    } else {
      setDecision({ kind: 'error', tier: 'HIGH', message: data.detection?.message || 'Verification failed.', explanationSource: 'deterministic' })
    }    setOtpHold(null)
    setStep(4)
  }

  return (
    <PhoneFrame showNav={step !== 4}>
      <div style={{ padding: 20 }}>
        {step > 1 && step < 4 && (
          <button onClick={() => setStep(step - 1)} style={backBtn}>&larr; Back</button>
        )}

        {step === 1 && (
          <StepRecipient
            beneficiary={beneficiary} setBeneficiary={setBeneficiary}
            capture={capture} onNext={() => setStep(2)}
          />
        )}
        {step === 2 && (
          <StepAmount amount={amount} setAmount={setAmount} capture={capture} onNext={() => setStep(3)} />
        )}
        {step === 3 && (
          <StepReview
            beneficiary={beneficiary} amount={amount} loading={loading}
            onConfirm={handleConfirm} honeytoken={honeytoken} setHoneytoken={setHoneytoken}
          />
        )}
        {step === 5 && otpHold && (
          <StepOtp otp={otp} setOtp={setOtp} demoOtp={otpHold.demoOtp} loading={loading} onVerify={handleVerify} />
        )}
        {step === 4 && decision && (
          <StepResult decision={decision} onDone={() => navigate('/bank/home')} />
        )}
      </div>
    </PhoneFrame>
  )
}

function StepRecipient({ beneficiary, setBeneficiary, capture, onNext }) {
  return (
    <div>
      <h2 style={h2}>Send to</h2>
      <input
        value={beneficiary} onChange={(e) => setBeneficiary(e.target.value)}
        onKeyDown={capture.onKeyDown} onKeyUp={capture.onKeyUp} onPaste={capture.onPaste}
        placeholder="Account number" style={inputStyle} autoFocus
      />
      <div style={{ marginTop: 20, fontSize: 12, color: 'var(--bank-ink-dim)', marginBottom: 8 }}>Recent</div>
      {RECENTS.map(r => (
        <button key={r.account} onClick={() => setBeneficiary(r.account)} style={chipStyle}>
          {r.name}
        </button>
      ))}
      <button disabled={!beneficiary} onClick={onNext} style={{ ...primaryBtn, marginTop: 24, opacity: beneficiary ? 1 : 0.4 }}>
        Continue
      </button>
    </div>
  )
}

function StepAmount({ amount, setAmount, capture, onNext }) {
  return (
    <div>
      <h2 style={h2}>Amount</h2>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, margin: '32px 0' }}>
        <span style={{ fontSize: 26, color: 'var(--bank-ink-dim)' }}>&#8358;</span>
        <input
          value={amount} onChange={(e) => setAmount(e.target.value)}
          onKeyDown={capture.onKeyDown} onKeyUp={capture.onKeyUp} onPaste={capture.onPaste}
          placeholder="0" autoFocus
          style={{ border: 'none', fontSize: 46, fontFamily: 'var(--font-display)', fontWeight: 700, width: '100%', outline: 'none' }}
        />
      </div>
      <button disabled={!amount} onClick={onNext} style={{ ...primaryBtn, opacity: amount ? 1 : 0.4 }}>
        Continue
      </button>
    </div>
  )
}

function StepReview({ beneficiary, amount, loading, onConfirm, honeytoken, setHoneytoken }) {
  return (
    <div>
      <h2 style={h2}>Review</h2>
      <div style={{ background: '#fff', border: '1px solid var(--bank-border)', borderRadius: 12, padding: 18, marginBottom: 26 }}>
        <Row label="To" value={beneficiary} />
        <Row label="Amount" value={`\u20a6${parseFloat(amount || 0).toLocaleString()}`} />
      </div>

      {/* Division 8B honeytoken - hidden field; only a bot that auto-fills every field populates it */}
      <input
        type="text" name="confirm_email_address" value={honeytoken}
        onChange={(e) => setHoneytoken(e.target.value)} tabIndex={-1} autoComplete="off"
        style={{ position: 'absolute', left: '-9999px', width: 1, height: 1, opacity: 0 }} aria-hidden="true"
      />

      <button onClick={onConfirm} disabled={loading} style={primaryBtn}>
        {loading ? 'Processing\u2026' : 'Confirm & send'}
      </button>
    </div>
  )
}

function StepOtp({ otp, setOtp, demoOtp, loading, onVerify }) {
  return (
    <div>
      <h2 style={h2}>Enter OTP</h2>
      <p style={{ color: 'var(--bank-ink-dim)', fontSize: 13, marginBottom: 14 }}>
        We sent a 6-digit code to your phone to verify this transfer.
      </p>
      {demoOtp && (
        <div style={{ background: '#FFF7E6', border: '1px solid var(--bank-orange)', borderRadius: 10, padding: '10px 14px', fontSize: 13, marginBottom: 16 }}>
          Demo code: <strong>{demoOtp}</strong>
        </div>
      )}
      <input
        value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
        placeholder="6-digit code" inputMode="numeric" autoFocus
        style={{ ...inputStyle, textAlign: 'center', fontSize: 22, letterSpacing: 6 }}
      />
      <button onClick={onVerify} disabled={loading || otp.length !== 6} style={{ ...primaryBtn, marginTop: 20, opacity: otp.length === 6 && !loading ? 1 : 0.4 }}>
        {loading ? 'Processing\u2026' : 'Verify & send'}
      </button>
    </div>
  )
}

function StepResult({ decision, onDone }) {
  const kind = decision.kind || (decision.tier?.toUpperCase() === 'HIGH' ? 'blocked' : decision.tier?.toUpperCase() === 'MEDIUM' ? 'challenge' : 'success')
  const config = {
    success:   { icon: '✓', color: 'var(--verdict-low)',    title: 'Sent' },
    challenge: { icon: '!', color: 'var(--verdict-medium)', title: 'We need to verify it’s you' },
    blocked:   { icon: '✕', color: 'var(--verdict-high)',  title: 'We stopped this transfer' },
    error:     { icon: '!', color: 'var(--verdict-medium)', title: 'Transfer could not be completed' },
  }[kind]

  const sourceLabel = {
    gemini: 'Gemini rewrite',
    ollama: 'Ollama rewrite',
    deterministic: 'Deterministic explanation',
    groq: 'Groq rewrite',
    deterministic_fallback: 'Deterministic fallback',
  }[decision.explanationSource] || 'Explanation'

  return (
    <div style={{ textAlign: 'center', paddingTop: 56 }}>
      <div style={{
        width: 76, height: 76, borderRadius: '50%', background: config.color,
        color: '#fff', fontSize: 34, display: 'flex', alignItems: 'center', justifyContent: 'center',
        margin: '0 auto 20px'
      }}>
        {config.icon}
      </div>
      <h2 style={h2}>{config.title}</h2>
      <p style={{ color: 'var(--bank-ink-dim)', fontSize: 14, maxWidth: 280, margin: '12px auto 8px' }}>
        {decision.explanation || decision.message}
      </p>
      {kind === 'blocked' && decision.blockedUntil ? (
        <p style={{ color: 'var(--verdict-high)', fontSize: 13, fontWeight: 600, margin: '0 auto 30px' }}>
          Blocked until {new Date(decision.blockedUntil).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      ) : null}
      <div style={{ fontSize: 11, color: 'var(--bank-ink-dim)', marginBottom: 16 }}>
        {sourceLabel}
      </div>
      <button onClick={onDone} style={primaryBtn}>Done</button>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', fontSize: 14 }}>
      <span style={{ color: 'var(--bank-ink-dim)' }}>{label}</span>
      <span style={{ fontWeight: 600 }}>{value}</span>
    </div>
  )
}

const h2 = { fontSize: 24, fontWeight: 700, marginBottom: 18 }
const backBtn = { background: 'none', border: 'none', color: 'var(--bank-ink-dim)', fontSize: 13, cursor: 'pointer', marginBottom: 14, padding: 0 }
const inputStyle = { width: '100%', padding: '14px', borderRadius: 10, border: '1px solid var(--bank-border)', fontSize: 16 }
const chipStyle = { background: '#fff', border: '1px solid var(--bank-border)', borderRadius: 20, padding: '8px 16px', fontSize: 13, marginRight: 8, cursor: 'pointer' }
const primaryBtn = { width: '100%', padding: 15, background: 'var(--bank-orange)', color: '#fff', border: 'none', borderRadius: 10, fontSize: 16, fontWeight: 600, cursor: 'pointer' }