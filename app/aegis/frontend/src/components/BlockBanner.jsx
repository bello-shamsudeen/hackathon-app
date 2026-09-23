import { useEffect, useState } from 'react'

// Division 9D - block countdown banner. Mounted once inside DemoHub, so it
// covers BANK (web), USSD simulator and FALLBACK ENGINE in one place. Any
// channel's block sets the same server-side blocked_until; transfers light
// it instantly via the 'aegis:blocked' window event, and a 30s dashboard
// poll keeps it in sync (e.g. blocks raised over USSD).
export default function BlockBanner({ session }) {
  const [blockedUntil, setBlockedUntil] = useState(null)
  const [now, setNow] = useState(Date.now())

  const sync = async () => {
    if (!session?.session_id) return
    try {
      const r = await fetch(`/bank/dashboard/${session.session_id}`)
      if (!r.ok) return
      const d = await r.json()
      setBlockedUntil(d.blocked_until || null)
    } catch { /* server unreachable - keep current state */ }
  }

  useEffect(() => {
    sync()
    const poll = setInterval(sync, 30000)
    const onBlocked = (e) => { e.detail ? setBlockedUntil(e.detail) : sync() }
    window.addEventListener('aegis:blocked', onBlocked)
    return () => { clearInterval(poll); window.removeEventListener('aegis:blocked', onBlocked) }
  }, [session])

  const target = blockedUntil ? new Date(blockedUntil).getTime() : 0
  const remaining = Math.max(0, Math.floor((target - now) / 1000))

  // 1s heartbeat only while blocked
  useEffect(() => {
    if (!blockedUntil) return undefined
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [blockedUntil])

  // hit zero -> confirm with the server, then dissolve
  useEffect(() => {
    if (blockedUntil && remaining <= 0) {
      setBlockedUntil(null)
      sync()
    }
  }, [remaining])

  if (!blockedUntil || remaining <= 0) return null

  const hh = String(Math.floor(remaining / 3600)).padStart(2, '0')
  const mm = String(Math.floor((remaining % 3600) / 60)).padStart(2, '0')
  const ss = String(remaining % 60).padStart(2, '0')

  return (
    <div className="block-banner" role="alert">
      <style>{`
        .block-banner {
          position: relative; z-index: 5;
          display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
          background: linear-gradient(90deg, #6E1B23 0%, #D64550 100%);
          color: #fff; padding: 12px 16px 12px 72px;
          box-shadow: 0 2px 14px rgba(0,0,0,0.4);
          animation: block-banner-in 0.35s ease;
        }
        @keyframes block-banner-in { from { opacity: 0; } to { opacity: 1; } }
        .block-banner-icon { font-size: 20px; animation: block-banner-blink 1.6s ease-in-out infinite; }
        @keyframes block-banner-blink { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
        .block-banner-text { display: flex; flex-direction: column; line-height: 1.3; min-width: 0; }
        .block-banner-text strong { font-size: 14px; }
        .block-banner-text span { font-size: 11px; color: rgba(255,255,255,0.75); }
        .block-banner-countdown {
          margin-left: auto; font-family: var(--font-mono, monospace);
          font-size: 20px; font-weight: 700; letter-spacing: 2px;
          background: rgba(0,0,0,0.35); padding: 6px 14px; border-radius: 8px;
        }
        @media (max-width: 560px) {
          .block-banner { padding-left: 66px; gap: 8px; }
          .block-banner-text strong { font-size: 12px; }
          .block-banner-text span { font-size: 10px; }
          .block-banner-countdown { font-size: 16px; padding: 5px 10px; width: 100%; text-align: center; margin-left: 0; }
        }
      `}</style>
      <span className="block-banner-icon" aria-hidden="true">&#128683;</span>
      <div className="block-banner-text">
        <strong>You have been blocked until {new Date(target).toLocaleTimeString()}</strong>
        <span>Transfers are locked on all channels for your security</span>
      </div>
      <div className="block-banner-countdown">{hh}:{mm}:{ss}</div>
    </div>
  )
}
