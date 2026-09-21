const FOUNDERS = [
  { name: 'Alebiosu Kareem', role: 'Product Design & Integration' },
  { name: 'Shamsudeen Bello', role: 'Backend Lead' },
  { name: 'Divine Ezeh', role: 'ML / Detection' },
]

const COLORS = ['#FF6A00', '#4FD1C5', '#6E5AC8']

function initials(name) {
  return name.split(' ').slice(0, 2).map(p => p[0]).join('')
}

export function FoundersSection() {
  return (
    <section className="founders-section" style={{ maxWidth: 900, margin: '0 auto', padding: '0 48px 100px' }}>
      <h2 style={{ fontSize: 28, marginBottom: 40 }}>Built by</h2>
      <div className="founders-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24 }}>
        {FOUNDERS.map((f, i) => (
          <div key={f.name} style={{
            border: '1px solid var(--ops-border)', borderRadius: 12, padding: 24, textAlign: 'center'
          }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%', background: COLORS[i],
              color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 22, margin: '0 auto 16px'
            }}>
              {initials(f.name)}
            </div>
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>{f.name}</div>
            <div style={{ color: 'var(--ops-text-dim)', fontSize: 13 }}>{f.role}</div>
          </div>
        ))}
      </div>
      <style>{`
        @media (max-width: 768px) {
          .founders-section {
            padding-left: 20px !important;
            padding-right: 20px !important;
          }
          .founders-grid {
            grid-template-columns: 1fr !important;
            gap: 16px !important;
          }
        }
      `}</style>
    </section>
  )
}
