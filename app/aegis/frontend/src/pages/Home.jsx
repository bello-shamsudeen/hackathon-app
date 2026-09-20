import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PhoneFrame from '../components/PhoneFrame'
import Avatar from '../components/Avatar'
import { useBehaviorCapture } from '../hooks/useBehaviorCapture'

const VERDICT_DOT = { ALLOW: '#1B8A5A', CHALLENGE: '#D89614', BLOCK: '#D64550' }

export default function Home({ session, showColdStartHint, dismissColdStartHint }) {
  const [balance, setBalance] = useState(null)
  const [recent, setRecent] = useState([])
  const capture = useBehaviorCapture(session?.session_id)
  const navigate = useNavigate()

  useEffect(() => {
    capture.trackNav('DASHBOARD')
    if (!session) { navigate('/bank'); return }
    fetch(`/bank/dashboard/${session.session_id}`).then(r => r.json()).then(setBalance)
    fetch(`/bank/transactions/${session.user_id}`).then(r => r.json())
      .then(data => setRecent(data.transactions.slice(0, 4)))
  }, [session])

  if (!session) return null

  return (
    <PhoneFrame>
      <div style={{ padding: 22 }} onMouseMove={capture.onMouseMove}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 }}>
          <div>
            <div style={{ fontSize: 14, color: 'var(--bank-ink-dim)' }}>Hi,</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-display)' }}>{session.full_name}</div>
          </div>
          <Avatar name={session.full_name} photoUrl={session.avatar_data_url} onClick={() => navigate('/bank/profile')} />
        </div>

        {showColdStartHint && (
          <div style={{
            background: 'var(--verdict-medium-bg)', color: '#8A6200', fontSize: 13,
            padding: '12px 16px', borderRadius: 8, marginBottom: 18, display: 'flex',
            justifyContent: 'space-between', alignItems: 'center'
          }}>
            <span>New accounts get extra verification on early transactions.</span>
            <button onClick={dismissColdStartHint} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#8A6200', fontWeight: 700 }}>&times;</button>
          </div>
        )}

        <div style={{
          background: 'var(--bank-navy-900)', color: '#fff', borderRadius: 14, padding: 26, marginBottom: 22
        }}>
          <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.6)', marginBottom: 8 }}>Available balance</div>
          {balance && (
            <div style={{ fontSize: 34, fontFamily: 'var(--font-display)', fontWeight: 700 }}>
              &#8358;{balance.balance.toLocaleString()}
            </div>
          )}
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', marginTop: 12 }} className="mono">
            &#8226;&#8226;&#8226;&#8226; {session.account_number?.slice(-4)}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 26 }}>
          <Tile label="Send" icon="&#8593;" onClick={() => navigate('/bank/send')} />
          <Tile label="Airtime" icon="&#128241;" />
          <Tile label="Bills" icon="&#128196;" />
          <Tile label="History" icon="&#128337;" onClick={() => navigate('/bank/history')} />
          <Tile label="USSD Demo" icon="&#128222;" onClick={() => navigate('/bank/ussd')} />
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 9, fontSize: 13, color: 'var(--bank-ink-dim)', marginBottom: 18 }}>
          <input type="checkbox" onChange={(e) => capture.setCallActive(e.target.checked)} />
          I'm currently on a phone call (demo toggle)
        </label>

        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Recent activity</div>
        {recent.map(tx => (
          <div key={tx.id} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '14px 0', borderBottom: '1px solid var(--bank-border)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
              <span style={{ width: 9, height: 9, borderRadius: '50%', background: VERDICT_DOT[tx.verdict] || VERDICT_DOT.ALLOW }} />
              <span style={{ fontSize: 14 }}>{tx.beneficiary_account}</span>
            </div>
            <span style={{ fontSize: 14, fontWeight: 600 }} className="mono">-&#8358;{tx.amount.toLocaleString()}</span>
          </div>
        ))}
        {recent.length === 0 && (
          <div style={{ fontSize: 14, color: 'var(--bank-ink-dim)', padding: '22px 0', textAlign: 'center' }}>
            No transactions yet
          </div>
        )}
      </div>
    </PhoneFrame>
  )
}

function Tile({ label, icon, onClick }) {
  return (
    <button onClick={onClick} style={{
      background: '#fff', border: '1px solid var(--bank-border)', borderRadius: 12,
      padding: '16px 5px', cursor: onClick ? 'pointer' : 'default', display: 'flex',
      flexDirection: 'column', alignItems: 'center', gap: 7
    }}>
      <span style={{ fontSize: 21 }}>{icon}</span>
      <span style={{ fontSize: 12, fontWeight: 600 }}>{label}</span>
    </button>
  )
}