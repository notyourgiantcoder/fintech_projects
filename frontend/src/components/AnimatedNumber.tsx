import { useEffect, useRef, useState } from 'react'

const DURATION_MS = 420

function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

/** Tweens to a new value so a changed input visibly changes the figure it drives. */
export function AnimatedNumber({ value, format }: { value: number; format: (n: number) => string }) {
  const [shown, setShown] = useState(value)
  const from = useRef(value)

  useEffect(() => {
    if (prefersReducedMotion() || from.current === value) {
      from.current = value
      // Synchronising to an external animation clock is what this effect is for.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShown(value)
      return
    }
    const start = performance.now()
    const begin = from.current
    let frame = 0
    const tick = (now: number) => {
      const t = Math.min((now - start) / DURATION_MS, 1)
      const eased = 1 - (1 - t) ** 3
      setShown(begin + (value - begin) * eased)
      if (t < 1) frame = requestAnimationFrame(tick)
      else from.current = value
    }
    frame = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(frame)
      from.current = value
    }
  }, [value])

  return <>{format(shown)}</>
}
