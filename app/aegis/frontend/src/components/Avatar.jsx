/**
 * Division 9A-revised — Avatar.
 * Shows a real photo if one exists, otherwise a colored initials circle
 * generated deterministically from the name (same name always gets the
 * same color, so it feels consistent rather than random each render).
 */
const COLORS = ['#FF6A00', '#14335C', '#1B8A5A', '#6E5AC8', '#D64550', '#0B7285']

function colorForName(name) {
  const sum = [...(name || '')].reduce((acc, ch) => acc + ch.charCodeAt(0), 0)
  return COLORS[sum % COLORS.length]
}

export default function Avatar({ name, photoUrl, size = 40, onClick }) {
  const initials = (name || '?').split(' ').slice(0, 2).map(p => p[0]?.toUpperCase()).join('')

  if (photoUrl) {
    return (
      <img
        src={photoUrl} alt={name} onClick={onClick}
        style={{
          width: size, height: size, borderRadius: '50%', objectFit: 'cover',
          cursor: onClick ? 'pointer' : 'default', border: '2px solid rgba(255,255,255,0.2)'
        }}
      />
    )
  }

  return (
    <div
      onClick={onClick}
      style={{
        width: size, height: size, borderRadius: '50%', background: colorForName(name),
        color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: size * 0.4,
        cursor: onClick ? 'pointer' : 'default', flexShrink: 0
      }}
    >
      {initials}
    </div>
  )
}
