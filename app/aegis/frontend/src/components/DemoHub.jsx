import { useState, useEffect } from 'react'
import BlockBanner from './BlockBanner'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'

const DEMOS = [
  { path: '/bank/home', label: 'BANK' },
  { path: '/bank/ussd', label: 'USSD' },
  { path: '/demo/manual', label: 'FALLBACK ENGINE', engine: true },
]

const DOT = {
  active:  { color: '#2ECC71', label: 'ACTIVE', pulse: true },
  standby: { color: '#D64550', label: 'STANDBY', pulse: false },
  unknown: { color: '#7A8A90', label: '...', pulse: false },
}

export default function DemoHub({ session }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [engine, setEngine] = useState('unknown')

  useEffect(() => {
    let stop = false
    const probe = async () => {
      try {
        const res = await fetch('/score/engine-status')
        if (!res.ok) throw new Error('bad status')
        const data = await res.json()
        if (!stop) setEngine(data.fallback_active ? 'active' : 'standby')
      } catch (e) {
        if (!stop) setEngine('unknown')
      }
    }
    probe()
    const t = setInterval(probe, 10000)
    return () => { stop = true; clearInterval(t) }
  }, [])

  const isActive = (path) => {
    if (path === '/bank/ussd') return location.pathname.startsWith('/bank/ussd')
    if (path === '/demo/manual') return location.pathname.startsWith('/demo/manual')
    return location.pathname.startsWith('/bank') && !location.pathname.startsWith('/bank/ussd')
  }

  const go = (path) => { navigate(path); setOpen(false) }
  const dot = DOT[engine] || DOT.unknown

  return (
    <div className="demo-hub">
      <style>{`
        .demo-hub { min-height: 100vh; background: var(--bank-navy-900); }
        .demo-hub-hamburger {
          position: fixed; top: 18px; left: 18px; z-index: 120;
          width: 44px; height: 44px; border-radius: 10px;
          background: rgba(13,21,23,0.85); border: 1px solid rgba(255,255,255,0.25);
          color: #fff; font-size: 20px; cursor: pointer; line-height: 1;
        }
        .demo-hub-hamburger:hover { border-color: #fff; }
        .demo-hub-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); z-index: 110; }
        .demo-hub-drawer {
          position: fixed; left: 0; top: 0; bottom: 0; width: 240px; z-index: 130;
          background: #0D1517; border-right: 1px solid rgba(255,255,255,0.12);
          transform: translateX(-100%); transition: transform 0.22s ease;
          display: flex; flex-direction: column; padding-top: 76px;
        }
        .demo-hub-drawer.open { transform: translateX(0); }
        .demo-hub-item {
          display: flex; align-items: center; justify-content: space-between;
          background: none; border: none; border-left: 3px solid transparent;
          color: rgba(255,255,255,0.75); padding: 16px 20px; cursor: pointer;
          font-size: 13px; font-weight: 700; letter-spacing: 2px; text-align: left;
          font-family: var(--font-mono, monospace); width: 100%;
        }
        .demo-hub-item:hover { color: #fff; background: rgba(255,255,255,0.05); }
        .demo-hub-item.active {
          color: #fff; border-left-color: var(--ops-accent, #4FD1C5);
          background: rgba(79,209,197,0.10);
        }
        .demo-hub-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
        .demo-hub-dot-pulse { animation: demo-hub-pulse 1.4s ease-in-out infinite; }
        @keyframes demo-hub-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .demo-hub-content { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
      `}</style>

      <button className="demo-hub-hamburger" onClick={() => setOpen(o => !o)} onMouseEnter={() => setOpen(true)} aria-label="menu">&#9776;</button>

      <aside className={'demo-hub-drawer' + (open ? ' open' : '')} onMouseLeave={() => setOpen(false)}>
        {DEMOS.map(d => (
          <button key={d.path} className={'demo-hub-item' + (isActive(d.path) ? ' active' : '')} onClick={() => go(d.path)}>
            <span>{d.label}</span>
            {d.engine && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: dot.color }}>{dot.label}</span>
                <span className={dot.pulse ? 'demo-hub-dot demo-hub-dot-pulse' : 'demo-hub-dot'} style={{ background: dot.color }} />
              </span>
            )}
          </button>
        ))}
      </aside>

      {open && <div className="demo-hub-overlay" onClick={() => setOpen(false)} />}

      <BlockBanner session={session} />

      <main className="demo-hub-content"><Outlet /></main>
    </div>
  )
}