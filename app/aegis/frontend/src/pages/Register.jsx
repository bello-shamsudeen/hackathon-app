import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Avatar from '../components/Avatar'

export default function Register({ onRegistered }) {
  const [step, setStep] = useState(1)
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [pin, setPin] = useState('')
  const [nin, setNin] = useState('')
  const [bvn, setBvn] = useState('')
  const [photo, setPhoto] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const res = await fetch('/bank/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName, phone_number: phone, pin, nin, bvn, avatar_data_url: photo })
      })
      if (!res.ok) {
        const errData = await res.json()
        const msg = Array.isArray(errData.detail)
          ? errData.detail.map(d => (d.loc ? d.loc[d.loc.length - 1] + ': ' : '') + d.msg).join(', ')
          : (errData.detail || 'Registration failed. Please check your details and try again.')
        setError(msg)
        setSubmitting(false)
        return
      }
      const data = await res.json()
      onRegistered({ ...data, avatar_data_url: photo })
      navigate('/bank/home')
    } catch (err) {
      setError('Could not reach the server. Please check your connection and try again.')
      setSubmitting(false)
    }
  }

  return (
    <div className="theme-bank" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 380 }}>
        <div style={{ display: 'flex', gap: 6, marginBottom: 28 }}>
          {[1, 2, 3].map(i => (
            <div key={i} style={{ flex: 1, height: 4, borderRadius: 2, background: i <= step ? 'var(--bank-orange)' : 'var(--bank-border)' }} />
          ))}
        </div>

        {step === 1 && (
          <StepOne fullName={fullName} setFullName={setFullName} phone={phone} setPhone={setPhone}
            pin={pin} setPin={setPin}
            onNext={() => setStep(2)} />
        )}
        {step === 2 && (
          <StepTwo nin={nin} setNin={setNin} bvn={bvn} setBvn={setBvn}
            onBack={() => setStep(1)} onNext={() => setStep(3)} />
        )}
        {step === 3 && (
          <StepThree fullName={fullName} photo={photo} setPhoto={setPhoto}
            onBack={() => setStep(2)} onSubmit={handleSubmit} submitting={submitting} error={error} />
        )}
      </div>
    </div>
  )
}

function StepOne({ fullName, setFullName, phone, setPhone, pin, setPin, onNext }) {
  return (
    <div>
      <h1 style={h1}>Let's get you set up</h1>
      <p style={subtitle}>Simulated account &#8226; made-up data only</p>
      <Field label="Full name" value={fullName} onChange={setFullName} placeholder="e.g. Sees Hacks" />
      <Field label="Phone number" value={phone} onChange={setPhone} placeholder="080XXXXXXXX" />
      <Field label="Choose a 4-digit PIN" value={pin} onChange={(v) => setPin(v.replace(/\D/g, '').slice(0, 4))} placeholder="0000" type="password" inputMode="numeric" />
      <button disabled={!fullName || !phone || pin.length !== 4} onClick={onNext} style={{ ...btn, opacity: fullName && phone && pin.length === 4 ? 1 : 0.4 }}>
        Continue
      </button>
    </div>
  )
}

function StepTwo({ nin, setNin, bvn, setBvn, onBack, onNext }) {
  return (
    <div>
      <button onClick={onBack} style={backBtn}>&larr; Back</button>
      <h1 style={h1}>Verify your identity</h1>
      <p style={subtitle}>Any values work &mdash; this is a demo</p>
      <Field label="NIN" value={nin} onChange={setNin} placeholder="11 digits" />
      <Field label="BVN" value={bvn} onChange={setBvn} placeholder="11 digits" />
      <button disabled={!nin || !bvn} onClick={onNext} style={{ ...btn, opacity: nin && bvn ? 1 : 0.4 }}>
        Continue
      </button>
    </div>
  )
}

function StepThree({ fullName, photo, setPhoto, onBack, onSubmit, submitting, error }) {
  const [showCamera, setShowCamera] = useState(false)
  const videoRef = useRef(null)
  const streamRef = useRef(null)

  const startCamera = async () => {
    setShowCamera(true)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true })
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
    } catch {
      setShowCamera(false)
      alert('Camera unavailable \u2014 try uploading a photo instead.')
    }
  }

  const capture = () => {
    const canvas = document.createElement('canvas')
    canvas.width = videoRef.current.videoWidth
    canvas.height = videoRef.current.videoHeight
    canvas.getContext('2d').drawImage(videoRef.current, 0, 0)
    setPhoto(canvas.toDataURL('image/jpeg'))
    streamRef.current?.getTracks().forEach(t => t.stop())
    setShowCamera(false)
  }

  const handleFileUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setPhoto(reader.result)
    reader.readAsDataURL(file)
  }

  return (
    <div>
      <button onClick={onBack} style={backBtn}>&larr; Back</button>
      <h1 style={h1}>Add a photo</h1>
      <p style={subtitle}>Optional &mdash; skip to use your initials instead</p>

      {showCamera ? (
        <div>
          <video ref={videoRef} autoPlay playsInline style={{ width: '100%', borderRadius: 12, marginBottom: 12 }} />
          <button onClick={capture} style={btn}>Capture</button>
        </div>
      ) : (
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <Avatar name={fullName} photoUrl={photo} size={104} />
        </div>
      )}

      {!showCamera && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
          <button onClick={startCamera} style={secondaryBtn}>Take photo</button>
          <label style={{ ...secondaryBtn, textAlign: 'center', cursor: 'pointer' }}>
            Upload
            <input type="file" accept="image/*" onChange={handleFileUpload} style={{ display: 'none' }} />
          </label>
        </div>
      )}

      {error && (
        <div style={{ background: '#FDECEC', color: '#B3261E', padding: '12px 14px', borderRadius: 8, fontSize: 13, marginBottom: 16 }}>
          {error}
        </div>
      )}

      <button onClick={onSubmit} disabled={submitting} style={btn}>
        {submitting ? 'Creating account\u2026' : 'Finish'}
      </button>
    </div>
  )
}

function Field({ label, value, onChange, placeholder, type = 'text', inputMode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>{label}</label>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} type={type} inputMode={inputMode}
        style={{ width: '100%', padding: '13px 14px', borderRadius: 8, border: '1px solid var(--bank-border)', fontSize: 15 }} />
    </div>
  )
}

const h1 = { fontSize: 28, fontWeight: 700, marginBottom: 6 }
const subtitle = { color: 'var(--bank-ink-dim)', fontSize: 14, marginBottom: 24 }
const btn = { width: '100%', padding: 14, background: 'var(--bank-orange)', color: '#fff', border: 'none', borderRadius: 8, fontSize: 16, fontWeight: 600, cursor: 'pointer', marginTop: 8 }
const secondaryBtn = { flex: 1, padding: 12, background: '#fff', border: '1px solid var(--bank-border)', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer' }
const backBtn = { background: 'none', border: 'none', color: 'var(--bank-ink-dim)', fontSize: 13, cursor: 'pointer', marginBottom: 14, padding: 0, display: 'block' }