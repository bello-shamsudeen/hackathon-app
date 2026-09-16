/**
 * Division 2 — behavioral telemetry capture.
 * This hook is the entire point of the fake bank existing. It watches
 * every keystroke, paste, backspace, and navigation change, batches them,
 * and streams them to /ingest/behavior. Attach it once per page via
 * useBehaviorCapture(sessionId).
 */
import { useEffect, useRef, useCallback } from 'react'

const FLUSH_INTERVAL_MS = 2000

export function useBehaviorCapture(sessionId) {
  const queue = useRef([])
  const lastKeyTime = useRef(null)
  const lastKeyDownTime = useRef(null)

  const push = useCallback((event) => {
    if (!sessionId) return
    queue.current.push({ session_id: sessionId, ...event })
  }, [sessionId])

  useEffect(() => {
    const flush = async () => {
      if (queue.current.length === 0) return
      const events = queue.current
      queue.current = []
      try {
        await fetch('/ingest/behavior', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ events })
        })
      } catch (e) {
        // Silent fail is intentional for the demo — we never want telemetry
        // failure to block the user's actual banking action.
        console.warn('behavior flush failed', e)
      }
    }
    const interval = setInterval(flush, FLUSH_INTERVAL_MS)
    return () => { clearInterval(interval); flush() }
  }, [])

  // --- Keystroke dwell/flight timing ---
  const onKeyDown = useCallback((e) => {
    const now = performance.now()
    lastKeyDownTime.current = now
    if (lastKeyTime.current !== null) {
      push({ event_type: 'KEYDOWN', key_flight_ms: Math.round(now - lastKeyTime.current) })
    }
    if (e.key === 'Backspace') {
      push({ event_type: 'BACKSPACE', backspace_count: 1 })
    }
  }, [push])

  const onKeyUp = useCallback(() => {
    const now = performance.now()
    if (lastKeyDownTime.current !== null) {
      push({ event_type: 'KEYUP', key_dwell_ms: Math.round(now - lastKeyDownTime.current) })
    }
    lastKeyTime.current = now
  }, [push])

  // --- Paste detection ---
  const onPaste = useCallback(() => {
    push({ event_type: 'PASTE', is_paste: true })
  }, [push])

  // --- Navigation tracking ---
  const trackNav = useCallback((screenName) => {
    push({ event_type: 'NAV', nav_screen: screenName })
  }, [push])

  // --- Cursor/touch smoothness (very rough placeholder metric for the demo) ---
  const lastMove = useRef(null)
  const onMouseMove = useCallback((e) => {
    const now = performance.now()
    if (lastMove.current) {
      const dt = now - lastMove.current.t
      const dx = e.clientX - lastMove.current.x
      const dy = e.clientY - lastMove.current.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      const speed = dt > 0 ? dist / dt : 0
      // crude smoothness proxy: extremely high instantaneous speed = less "human"
      const smoothness = Math.max(0, 1 - Math.min(speed / 5, 1))
      push({ event_type: 'MOUSEMOVE', cursor_smoothness_score: smoothness })
    }
    lastMove.current = { t: now, x: e.clientX, y: e.clientY }
  }, [push])

  // --- Simultaneous call flag (manual toggle for the demo; in production
  // this would come from a mobile SDK / telephony state, not the browser) ---
  const setCallActive = useCallback((active) => {
    push({ event_type: 'CALL_STATE', call_active: active })
  }, [push])

  return { onKeyDown, onKeyUp, onPaste, onMouseMove, trackNav, setCallActive }
}
