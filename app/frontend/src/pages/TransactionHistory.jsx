import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PhoneFrame from '../components/PhoneFrame'

const VERDICT_DOT = { ALLOW: '#1B8A5A', CHALLENGE: '#D89614', BLOCK: '#D64550' }
const FILTERS = ['All', 'Reviewed']

export default function TransactionHistory({ session }) {
  const [transactions, setTransactions] = useState([])
  const [filter, setFilter] = useState('All')
  const [selected, setSelected] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!session) { navigate('/bank'); return }
    fetch(`/bank/transactions/${session.user_id}`).then(r => r.json()).then(d => setTransactions(d.transactions))
  }, [session])

  if (!session) return null

  const filtered = filter === 'All' ? transactions : transactions.filter(t => t.verdict !== 'ALLOW')

  const grouped = filtered.reduce((acc, tx) => {
    const date = tx.date ? new Date(tx.date).toDateString() : 'Unknown'
    acc[date] = acc[date] || []
    acc[date].push(tx)
    return acc
  }, {})

  return (
    <PhoneFrame>
      <div style={{ padding: 20 }}>
        <h2 style={{ fontSize: 20, marginBottom: 16 }}>Transaction history</h2>

        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          {FILTERS.map(f => (
            <button
              key={f} onClick={() => setFilter(f)}
              style={{
                padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                border: f === filter ? 'none' : '1px solid var(--bank-border)',
                background: f === filter ? 'var(--bank-navy-900)' : '#fff',
                color: f === filter ? '#fff' : 'var(--bank-ink)'
              }}
            >
              {f}
            </button>
          ))}
        </div>

        {Object.entries(grouped).map(([date, txs]) => (
          <div key={date} style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 11, color: 'var(--bank-ink-dim)', marginBottom: 8 }}>{date}</div>
            {txs.map(tx => (
              <button
                key={tx.id} onClick={() => setSelected(tx)}
                style={{
                  width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '12px 0', borderBottom: '1px solid var(--bank-border)', background: 'none',
                  border: 'none', borderBottomWidth: 1, borderBottomStyle: 'solid', borderBottomColor: 'var(--bank-border)',
                  cursor: 'pointer', textAlign: 'left'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: VERDICT_DOT[tx.verdict] || VERDICT_DOT.ALLOW }} />
                  <span style={{ fontSize: 13 }}>{tx.beneficiary_account}</span>
                </div>
                <span style={{ fontSize: 13, fontWeight: 600 }} className="mono">-&#8358;{tx.amount.toLocaleString()}</span>
              </button>
            ))}
          </div>
        ))}

        {filtered.length === 0 && (
          <div style={{ textAlign: 'center', color: 'var(--bank-ink-dim)', fontSize: 13, marginTop: 60 }}>
            Nothing here yet
          </div>
        )}
      </div>

      {/* Detail sheet */}
      {selected && (
        <div onClick={() => setSelected(null)} style={{
          position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)',
          display: 'flex', alignItems: 'flex-end'
        }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            background: '#fff', width: '100%', borderRadius: '20px 20px 0 0', padding: 24
          }}>
            <span className={`verdict-badge verdict-${selected.verdict?.toLowerCase()}`} style={{
              background: selected.verdict === 'BLOCK' ? 'var(--verdict-high-bg)' : selected.verdict === 'CHALLENGE' ? 'var(--verdict-medium-bg)' : 'var(--verdict-low-bg)',
              color: selected.verdict === 'BLOCK' ? 'var(--verdict-high)' : selected.verdict === 'CHALLENGE' ? 'var(--verdict-medium)' : 'var(--verdict-low)',
            }}>
              {selected.verdict}
            </span>
            <div style={{ fontSize: 24, fontWeight: 700, margin: '14px 0 6px', fontFamily: 'var(--font-display)' }}>
              &#8358;{selected.amount.toLocaleString()}
            </div>
            <div style={{ fontSize: 13, color: 'var(--bank-ink-dim)', marginBottom: 14 }}>To {selected.beneficiary_account}</div>
            {selected.message && (
              <p style={{ fontSize: 13, color: 'var(--bank-ink)', background: 'var(--bank-bg)', padding: 12, borderRadius: 8 }}>
                {selected.message}
              </p>
            )}
          </div>
        </div>
      )}
    </PhoneFrame>
  )
}
