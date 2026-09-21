import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import FeatureShowcase from '../components/landing/FeatureShowcase'
import FAQSection from '../components/landing/FAQSection'
import { FoundersSection } from '../components/landing/FoundersSection'

export default function Landing({ onLogin }) {
  const navigate = useNavigate()
  const [stage, setStage] = useState(0)

  useEffect(() => {
    const sequence = [0, 1, 2, 2, 2, 0]
    let i = 0
    const interval = setInterval(() => { i = (i + 1) % sequence.length; setStage(sequence[i]) }, 1400)
    return () => clearInterval(interval)
  }, [])

  const handleDemoLogin = async () => {
    const res = await fetch('/bank/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ msisdn: '08012345678', pin: '1234', device_fingerprint: 'demo-entry' })
    })
    const data = await res.json()
    onLogin(data)
    navigate('/bank/home')
  }

  return (
    <div className="theme-ops" style={{ minHeight: '100vh' }}>
      <style>{`
        .landing-header {
          display: flex; justify-content: space-between; align-items: center;
          padding: 24px 48px; border-bottom: 1px solid var(--ops-border);
        }
        .landing-hero {
          display: grid; grid-template-columns: 1fr 1fr; align-items: center;
          gap: 64px; padding: 48px; max-width: 1200px; margin: 0 auto;
        }
        .landing-h1 { font-size: 44px; line-height: 1.15; margin-bottom: 20px; max-width: 480px; }
        @media (max-width: 768px) {
          .landing-header { padding: 16px 20px; }
          .landing-hero { grid-template-columns: 1fr; gap: 32px; padding: 24px; }
          .landing-h1 { font-size: 28px; max-width: 100%; }
        }
      `}</style>

      <header className="landing-header">
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 20 }}>Aegis</div>
        <div style={{ color: 'var(--ops-text-dim)', fontSize: 14 }}>Built by SEES HACK for ICSC 2026</div>
      </header>

      <main className="landing-hero">
        <div>
          <h1 className="landing-h1">
            It checks the secret. Aegis checks the human.
          </h1>
          <p style={{ color: 'var(--ops-text-dim)', fontSize: 17, lineHeight: 1.6, maxWidth: 460, marginBottom: 32 }}>
            A behavioural trust engine for account takeover &mdash; watching how
            a transaction happens, not just whether the PIN was right.
          </p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <button onClick={handleDemoLogin} style={primaryBtn}>Try the SEES HACKS demo account</button>
            <button onClick={() => navigate('/register')} style={secondaryBtn}>Register your own account</button>
            <button onClick={() => navigate('/bank')} style={secondaryBtn}>Log in</button>
          </div>
        </div>

        <div style={{ background: 'var(--ops-panel)', border: '1px solid var(--ops-border)', borderRadius: 12, padding: 24, fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          <div style={{ color: 'var(--ops-text-dim)', marginBottom: 16, fontSize: 12 }}>live_feed.session_4471</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 0', borderBottom: '1px solid var(--ops-border)' }}>
            <span>Transfer &#8226; NGN 45,000</span>
            {stage === 0 && <span style={{ color: 'var(--ops-text-dim)' }}>pending&hellip;</span>}
            {stage === 1 && <span style={{ color: 'var(--ops-accent)' }}>scoring&hellip;</span>}
            {stage === 2 && <span className="verdict-badge verdict-high">BLOCKED</span>}
          </div>
          <div style={{ marginTop: 16, minHeight: 60, color: 'var(--ops-text-dim)', opacity: stage === 2 ? 1 : 0, transition: 'opacity 0.4s ease' }}>
            {stage === 2 && (
              <>
                <div style={{ marginBottom: 6 }}>risk_score: <span style={{ color: '#fff' }}>22.6</span> (behaviour looked normal)</div>
                <div>override: <span style={{ color: 'var(--verdict-high)' }}>SIM_SWAP_MODULE</span></div>
                <div style={{ marginTop: 10, color: 'var(--ops-text)' }}>
                  "SIM was recently changed and this device hasn't been used on your account before."
                </div>
              </>
            )}
          </div>
        </div>
      </main>

      <FeatureShowcase />
      <FAQSection />
      <FoundersSection />

      <footer style={{ borderTop: '1px solid var(--ops-border)', padding: '32px 48px', textAlign: 'center', color: 'var(--ops-text-dim)', fontSize: 13 }}>
        Aegis &mdash; Built by SEES HACK for ICSC 2026. Simulated demo environment.
      </footer>
    </div>
  )
}

const primaryBtn = { background: 'var(--ops-accent)', color: '#04201D', border: 'none', padding: '14px 22px', borderRadius: 8, fontSize: 15, fontWeight: 600, cursor: 'pointer' }
const secondaryBtn = { background: 'transparent', color: 'var(--ops-text)', border: '1px solid var(--ops-border)', padding: '14px 22px', borderRadius: 8, fontSize: 15, fontWeight: 600, cursor: 'pointer' }
