/**
 * Division 9A-revised - PhoneFrame.
 * Wraps bank screens in a stylized phone frame so the whole experience
 * reads as "real app" rather than "web form" - the single biggest visual
 * move for the startup-demo feel. Bottom nav is part of the frame itself
 * so every wrapped screen gets consistent navigation for free.
 *
 * Responsive: on real phones (max-width: 480px) the frame fills the
 * actual viewport instead of rendering as a fixed 390x780 mockup inside
 * a dark gutter - that fixed-size mockup is only meant to be seen on a
 * wider (desktop/tablet) browser.
 */
import { useNavigate, useLocation } from 'react-router-dom'

export default function PhoneFrame({ children, showNav = true }) {
  const navigate = useNavigate()
  const location = useLocation()

  const isActive = (path) => location.pathname === path

  return (
    <div className="phone-frame-wrapper">
      <style>{`
        .phone-frame-wrapper {
          min-height: 100vh;
          background: var(--bank-navy-900);
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
        }
        .phone-frame {
          width: 390px;
          height: 780px;
          background: var(--bank-bg);
          border-radius: 36px;
          box-shadow: 0 30px 80px rgba(0,0,0,0.5);
          overflow: hidden;
          display: flex;
          flex-direction: column;
          position: relative;
          border: 10px solid #0A0A0A;
        }
        @media (max-width: 480px) {
          .phone-frame-wrapper {
            padding: 0;
            min-height: 100dvh;
          }
          .phone-frame {
            width: 100%;
            height: 100dvh;
            border-radius: 0;
            border: none;
            box-shadow: none;
          }
        }
      `}</style>
      <div className="phone-frame">
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {children}
        </div>

        {showNav && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-around',
            padding: '14px 0 20px', background: '#fff', borderTop: '1px solid var(--bank-border)'
          }}>
            <NavIcon label="Home" active={isActive('/bank/home')} onClick={() => navigate('/bank/home')} icon={'\u2302'} />
            <SendButton onClick={() => navigate('/bank/send')} />
            <NavIcon label="History" active={isActive('/bank/history')} onClick={() => navigate('/bank/history')} icon={'\u2261'} />
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