import { useState } from 'react'

/**
 * Division 9A — FAQ.
 * Real questions a skeptical judge/technical reviewer would actually ask,
 * answered plainly and specifically rather than in marketing language.
 * Accordion motion is user-triggered (welcomed by design guidance) —
 * unlike the feature panels, this section stays quiet until interacted with.
 */
const FAQS = [
  {
    q: "Isn't this just another fraud-scoring model?",
    a: "The model is one layer. Underneath it are deterministic rules that never depend on the model being right \u2014 a SIM-swap check, a one-time-token system, a fraud-ring detector. If the model is wrong or unavailable, those still work."
  },
  {
    q: 'Does this replace the OTP?',
    a: "No \u2014 it recognises when the OTP alone isn't enough proof, specifically when the SIM behind it was recently swapped. In that case we don't just re-send another code to the same compromised number; we require a different verification path."
  },
  {
    q: 'What happens if the AI explanation layer goes down?',
    a: 'The plain-language explanation still gets generated \u2014 from the same underlying data, using a deterministic sentence template instead of a language model. Every fallback in the chain was tested by deliberately breaking the one before it.'
  },
  {
    q: 'Is any of this trained on real customer data?',
    a: "No. Every session, transaction, and behavioural pattern in this demo is synthetically generated, with the generation method documented. We treat that as a design constraint worth stating plainly, not hiding."
  },
  {
    q: "What doesn't Aegis catch well?",
    a: "Two attack patterns in our current testing \u2014 slow, patient drift under the transaction threshold, and impossible-travel detection \u2014 aren't yet strongly separated by the model. We'd rather say that than imply a perfect system."
  },
]

export default function FAQSection() {
  const [open, setOpen] = useState(0)

  return (
    <section style={{ maxWidth: 720, margin: '0 auto', padding: '60px 48px 100px' }}>
      <h2 style={{ fontSize: 28, marginBottom: 40 }}>Questions worth asking</h2>

      {FAQS.map((item, i) => (
        <div key={i} style={{ borderBottom: '1px solid var(--ops-border)' }}>
          <button
            onClick={() => setOpen(open === i ? -1 : i)}
            style={{
              width: '100%', textAlign: 'left', background: 'none', border: 'none',
              padding: '20px 0', display: 'flex', justifyContent: 'space-between',
              alignItems: 'center', cursor: 'pointer', color: 'var(--ops-text)'
            }}
          >
            <span style={{ fontSize: 16, fontWeight: 600 }}>{item.q}</span>
            <span style={{
              fontSize: 20, color: 'var(--ops-accent)',
              transform: open === i ? 'rotate(45deg)' : 'rotate(0deg)', transition: 'transform 0.2s'
            }}>+</span>
          </button>
          <div style={{
            maxHeight: open === i ? 200 : 0, overflow: 'hidden', transition: 'max-height 0.3s ease'
          }}>
            <p style={{ color: 'var(--ops-text-dim)', fontSize: 14, lineHeight: 1.65, paddingBottom: 20 }}>
              {item.a}
            </p>
          </div>
        </div>
      ))}
    </section>
  )
}
