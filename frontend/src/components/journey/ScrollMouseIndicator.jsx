import { useState, useEffect, useRef } from 'react';

/**
 * ScrollMouseIndicator — Side-positioned scroll-activated mouse indicator overlay.
 * - Appears on right edge ONLY while actively scrolling, fading out 1.5s after scroll stops.
 * - Detects scroll direction dynamically:
 *   - Scrolling DOWN → Wheel slides down, arrow points down (v).
 *   - Scrolling UP   → Wheel slides up, arrow points up (^).
 * - Clicking it scrolls to the next/previous section depending on current direction.
 */
export function ScrollMouseIndicator({ scrollRef, currentSection = 0, scrollOffset = 0 }) {
  const [isScrolling, setIsScrolling] = useState(false);
  const [scrollDirection, setScrollDirection] = useState('down');
  const timerRef = useRef(null);
  const prevScrollRef = useRef(scrollOffset);

  // Detect scroll offset changes & scroll direction ('down' vs 'up')
  useEffect(() => {
    if (scrollOffset > prevScrollRef.current + 0.002) {
      setScrollDirection('down');
    } else if (scrollOffset < prevScrollRef.current - 0.002) {
      setScrollDirection('up');
    }
    prevScrollRef.current = scrollOffset;

    setIsScrolling(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setIsScrolling(false);
    }, 1500);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [scrollOffset]);

  // Listen to native mouse wheel & scroll events for instant direction & visibility detection
  useEffect(() => {
    const handleWheel = (e) => {
      if (e.deltaY > 0) {
        setScrollDirection('down');
      } else if (e.deltaY < 0) {
        setScrollDirection('up');
      }

      setIsScrolling(true);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        setIsScrolling(false);
      }, 1500);
    };

    window.addEventListener('wheel', handleWheel, { passive: true });
    return () => window.removeEventListener('wheel', handleWheel);
  }, []);

  const isAtBottom = scrollOffset > 0.95;
  const isAtTop = scrollOffset < 0.02;
  const shouldShow = isScrolling && !(scrollDirection === 'down' && isAtBottom) && !(scrollDirection === 'up' && isAtTop);

  const handleClick = () => {
    let container = scrollRef?.current?.el;
    if (!container) {
      const candidates = document.querySelectorAll('div');
      for (const el of candidates) {
        const style = window.getComputedStyle(el);
        if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight) {
          container = el;
          break;
        }
      }
    }

    if (container) {
      const maxScroll = container.scrollHeight - container.clientHeight;
      const targetSectionIndex = scrollDirection === 'down' 
        ? Math.min(5, currentSection + 1)
        : Math.max(0, currentSection - 1);
      const targetOffset = targetSectionIndex * (1 / 5);

      container.scrollTo({
        top: maxScroll * targetOffset,
        behavior: 'smooth',
      });
    }
  };

  return (
    <div
      className="scroll-mouse-indicator"
      onClick={handleClick}
      style={{
        opacity: shouldShow ? 1 : 0,
        pointerEvents: shouldShow ? 'auto' : 'none',
        transform: `translateY(-50%) scale(${shouldShow ? 1 : 0.85})`,
      }}
      title={`Scroll ${scrollDirection}`}
      aria-label={`Scroll ${scrollDirection}`}
    >
      <div className="scroll-mouse-body">
        {/* Animated wheel dot: slides down when scrolling down, slides up when scrolling up */}
        <div className={`scroll-mouse-wheel scroll-mouse-wheel--${scrollDirection}`} />
      </div>
      {/* Arrow: points down when scrolling down, points up when scrolling up */}
      <div
        className="scroll-mouse-arrow"
        style={{
          transform: scrollDirection === 'down' ? 'rotate(45deg)' : 'rotate(-135deg)',
        }}
      />
    </div>
  );
}
