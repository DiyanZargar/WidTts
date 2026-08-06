import { useEffect, useState } from 'react';

/**
 * useReducedMotion — Accessibility hook.
 * Returns true when the user prefers reduced motion.
 * Used by both admin journey and user portal to disable shader animation.
 */
export function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const handler = (e) => setReduced(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return reduced;
}
