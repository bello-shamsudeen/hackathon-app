import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PhoneFrame from '../components/PhoneFrame'
import Avatar from '../components/Avatar'

export default function Profile({ session }) {
  const [profile, setProfile] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!session) { navigate('/bank'); return }
    fetch(`/bank/profile/${session.user_id}`).then(r => r.json()).then(setProfile)
  }, [session])

  if (!session || !profile) return null

  return (
    <PhoneFrame showNav={false}>
      <div style={{ padding: 20 }}>
        <button onClick={() => navigate('/bank/home')} style={{ background: 'none', border: 'none', color: 'var(--bank-ink-dim)', fontSize: 14, cursor: 'pointer', marginBottom: 20, padding: 0 }}>
          &larr; Back
        </button>

        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Avatar name={profile.full_name} photoUrl={profile.avatar_data_url} size={72} />
          <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-display)', marginTop: 12 }}>
            {profile.full_name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--bank-ink-dim)' }}>Member since {profile.member_since}</div>
        </div>

        <div style={{ background: '#fff', border: '1px solid var(--bank-border)', borderRadius: 12, overflow: 'hidden', marginBottom: 16 }}>
          <InfoRow label="Account number" value={profile.account_number} mono />
          <InfoRow label="Phone number" value={profile.phone_number} />
          <InfoRow label="NIN" value={profile.nin_masked} mono />
          <InfoRow label="BVN" value={profile.bvn_masked} mono last />
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px',
          background: 'var(--bank-navy-900)', borderRadius: 10, color: '#fff'
        }}>
          <span style={{ fontSize: 16 }}>&#128737;</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600 }}>Protected by Aegis</div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)' }}>Behavioural fraud monitoring, active</div>
          </div>
        </div>
      </div>
    </PhoneFrame>
  )
}

function InfoRow({ label, value, mono, last }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', padding: '14px 16px',
      borderBottom: last ? 'none' : '1px solid var(--bank-border)', fontSize: 13
    }}>
      <span style={{ color: 'var(--bank-ink-dim)' }}>{label}</span>
      <span className={mono ? 'mono' : ''} style={{ fontWeight: 600 }}>{value}</span>
    </div>
  )
}
