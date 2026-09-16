/**
 * Division 9A-revised — PhoneFrame.
 * Wraps bank screens in a stylized phone frame so the whole experience
 * reads as "real app" rather than "web form" — the single biggest visual
 * move for the startup-demo feel. Bottom nav is part of the frame itself
 * so every wrapped screen gets consistent navigation for free.
 */
import { useNavigate, useLocation } from 'react-router-dom'

export default function PhoneFrame({ children, showNav = true }) {
  const navigate = useNavigate()
  const location = useLocation()

  const isActive = (path) => location.pathname === path

  return (
    <div style={{
      minHeight: '100vh', background: 'var(--bank-navy-900)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24
    }}>
      <div style={{
        width: 390, height: 780, background: 'var(--bank-bg)', borderRadius: 36,
        boxShadow: '0 30px 80px rgba(0,0,0,0.5)', overflow: 'hidden',
        display: 'flex', flexDirection: 'column', position: 'relative',
        border: '10px solid #0A0A0A'
      }}>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {children}
        </div>

        {showNav && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-around',
            padding: '14px 0 20px', background: '#fff', borderTop: '1px solid var(--bank-border)'
          }}>
            <NavIcon label="Home" active={isActive('/bank/home')} onClick={() => navigate('/bank/home')} icon="\u2302" />
            <SendButton onClick={() => navigate('/bank/send')} />
            <NavIcon label="History" active={isActive('/bank/history')} onClick={() => navigate('/bank/history')} icon="\u2261" />
          </div>
        )}
      </div>
    </div>
  )
}

function NavIcon({ label, active, onClick, icon }) {
  return (
    <button onClick={onClick} style={{
      background: 'none', border: 'none', cursor: 'pointer', display: 'flex',
      flexDirection: 'column', alignItems: 'center', gap: 2,
      color: active ? 'var(--bank-orange)' : 'var(--bank-ink-dim)'
    }}>
      <span style={{ fontSize: 20 }}>{icon}</span>
      <span style={{ fontSize: 10, fontWeight: 600 }}>{label}</span>
    </button>
  )
}

function SendButton({ onClick }) {
  return (
    <button onClick={onClick} style={{
      width: 52, height: 52, borderRadius: '50%', background: 'var(--bank-orange)',
      color: '#fff', border: 'none', fontSize: 24, cursor: 'pointer',
      marginTop: -28, boxShadow: '0 6px 16px rgba(255,106,0,0.4)'
    }}>
      +
    </button>
  )
}
