import { useState, useEffect } from 'react'

/**
 * Division 9A - Feature Showcase.
 * DESIGN CHOICE: 4 features (not all 7 built), each with its own bespoke
 * animated micro-panel grounded in something actually proven in this build
 * - not a generic icon+text card grid. Alternating layout keeps a flat
 * "grid of cards" feeling from creeping in. Motion is per-panel, tied to
 * the real behavior it's demonstrating, not a blanket scroll-fade.
 */
export default function FeatureShowcase() {
  return (
    <section style={{ maxWidth: 1100, margin: '0 auto', padding: '80px 48px' }}>
      <style>{`
        @media (max-width: 768px) {
          .feature-row {
            grid-template-columns: 1fr !important;
            direction: ltr !important;
            gap: 24px !important;
          }
        }
      `}</style>
      <h2 style={{ fontSize: 32, marginBottom: 8, maxWidth: 560 }}>
        Four ways Aegis sees what a password can't
      </h2>
      <p style={{ color: 'var(--ops-text-dim)', fontSize: 16, marginBottom: 64, maxWidth: 520 }}>
        Every one of these is running in the live demo, not a mockup.
      </p>

      <FeatureRow reverse={false} title="Correct PIN. Correct OTP. Blocked anyway."
        body="A stolen SIM passes every credential check there is. Aegis checks whether the device has ever touched this account before - and whether the SIM moved recently. Neither alone means anything. Together, they mean everything.">
        <SimSwapPanel />
      </FeatureRow>

      <FeatureRow reverse={true} title="Built for the phone that isn't smart"
        body="No app. No JavaScript. No keystrokes to read. Aegis speaks the real USSD protocol banks use with telecom aggregators - the same interface, so it works unchanged behind a real telco connection.">
        <UssdPanel />
      </FeatureRow>

      <FeatureRow reverse={false} title="It notices when you're not really deciding"
        body="Most fraud in this market isn't a bot - it's a real person, on their own phone, being talked through a transfer by someone on the other end of a call. Aegis reads the hesitation, not just the outcome.">
        <CoachedPanel />
      </FeatureRow>

      <FeatureRow reverse={true} title="Ask it. It'll show its work."
        body="Every explanation is grounded in the same numbers that produced the decision - never invented. Ask a follow-up question and it answers from the real data, or tells you plainly when it doesn't know.">
        <CopilotPanel />
      </FeatureRow>
    </section>
  )
}

function FeatureRow({ title, body, children, reverse }) {
  return (
    <div className="feature-row" style={{
      display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 56, alignItems: 'center',
      marginBottom: 72, direction: reverse ? 'rtl' : 'ltr'
    }}>
      <div style={{ direction: 'ltr' }}>
        <h3 style={{ fontSize: 24, marginBottom: 14, lineHeight: 1.3 }}>{title}</h3>
        <p style={{ color: 'var(--ops-text-dim)', fontSize: 15, lineHeight: 1.65 }}>{body}</p>
      </div>
      <div style={{ direction: 'ltr' }}>{children}</div>
    </div>
  )
}

function PanelShell({ children, label }) {
  return (
    <div style={{
      background: 'var(--ops-panel)', border: '1px solid var(--ops-border)', borderRadius: 12,
      padding: 22, fontFamily: 'var(--font-mono)', fontSize: 13, minHeight: 180
    }}>
      <div style={{ color: 'var(--ops-text-dim)', fontSize: 11, marginBottom: 14 }}>{label}</div>
      {children}
    </div>
  )
}

function SimSwapPanel() {
  const [stage, setStage] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setStage(s => (s + 1) % 4), 1100)
    return () => clearInterval(id)
  }, [])
  return (
    <PanelShell label="session_4471 &mdash; auth_checks">
      <CheckLine label="PIN correct" done={stage >= 1} />
      <CheckLine label="OTP correct" done={stage >= 2} />
      <div style={{
        marginTop: 14, padding: '10px 12px', borderRadius: 8,
        background: stage >= 3 ? 'var(--verdict-high-bg)' : 'transparent',
        color: stage >= 3 ? 'var(--verdict-high)' : 'var(--ops-text-dim)',
        transition: 'all 0.3s ease', fontWeight: stage >= 3 ? 600 : 400
      }}>
        {stage >= 3 ? 'SIM swapped 2 days ago \u2014 BLOCKED' : 'checking device history\u2026'}
      </div>
    </PanelShell>
  )
}
function CheckLine({ label, done }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, opacity: done ? 1 : 0.35, transition: 'opacity 0.3s' }}>
      <span style={{ color: 'var(--verdict-low)' }}>{done ? '\u2713' : '\u25CB'}</span> {label}
    </div>
  )
}

function UssdPanel() {
  const [text, setText] = useState('')
  const full = 'CON Welcome to SEES HACK Bank\n1. Check Balance\n2. Send Money'
  useEffect(() => {
    let i = 0
    const id = setInterval(() => {
      setText(full.slice(0, i))
      i = i >= full.length ? 0 : i + 1
    }, 60)
    return () => clearInterval(id)
  }, [])
  return (
    <div style={{
      background: '#9ead86', color: '#1a1a1a', borderRadius: 10, padding: 20,
      fontFamily: 'var(--font-mono)', fontSize: 13, whiteSpace: 'pre-wrap', minHeight: 180
    }}>
      {text}<span style={{ opacity: 0.5 }}>&#9608;</span>
    </div>
  )
}

function CoachedPanel() {
  const [active, setActive] = useState(false)
  useEffect(() => {
    const id = setInterval(() => setActive(a => !a), 1500)
    return () => clearInterval(id)
  }, [])
  return (
    <PanelShell label="session_2290 &mdash; live signals">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <span>call_active</span>
        <span style={{ color: active ? 'var(--verdict-medium)' : 'var(--ops-text-dim)' }}>{active ? 'true' : 'false'}</span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <span>hesitation</span>
        <span style={{ color: active ? 'var(--verdict-medium)' : 'var(--ops-text-dim)' }}>{active ? '4.2s pause' : 'normal'}</span>
      </div>
      <div style={{
        marginTop: 14, padding: '10px 12px', borderRadius: 8,
        background: active ? 'var(--verdict-medium-bg)' : 'transparent',
        color: active ? 'var(--verdict-medium)' : 'var(--ops-text-dim)', transition: 'all 0.3s'
      }}>
        {active ? 'step-up requested \u2014 OTP valid, but coached' : 'monitoring\u2026'}
      </div>
    </PanelShell>
  )
}

function CopilotPanel() {
  const [chars, setChars] = useState(0)
  const answer = "Blocked because the SIM was swapped 2 days ago and this device hasn't been used on the account before."
  useEffect(() => {
    let i = 0
    const id = setInterval(() => { i = (i >= answer.length ? -20 : i + 1); setChars(Math.max(0, i)) }, 35)
    return () => clearInterval(id)
  }, [])
  return (
    <PanelShell label="ask_aegis">
      <div style={{ color: 'var(--ops-accent)', marginBottom: 10 }}>&gt; why was this blocked?</div>
      <div style={{ color: 'var(--ops-text)', lineHeight: 1.6 }}>{answer.slice(0, chars)}</div>
    </PanelShell>
  )
}