import { useNavigate } from 'react-router-dom';

const SECTIONS = [
  { id: 'overview', label: 'Overview', offset: 0 },
  { id: 'llm', label: 'LLM', offset: 0.167 },
  { id: 'speech', label: 'Speech', offset: 0.333 },
  { id: 'bot', label: 'Bot', offset: 0.5 },
  { id: 'deploy', label: 'Deploy', offset: 0.667 },
  { id: 'live', label: 'Live', offset: 0.833 },
];

/**
 * TopNav — Fixed transparent nav with 3D + 2D scroll-spy sync.
 * Has a solid background that fades to transparent at the bottom edge,
 * so content fades in smoothly as it scrolls underneath.
 */
export function TopNav({ scrollRef, currentSection = 0, visible = true }) {
  const navigate = useNavigate();

  const handleJumpTo = (index, offset) => {
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
      // Use actual section DOM position instead of hardcoded offset fraction.
      // This works correctly even when form sections grow taller than 100vh.
      const sections = document.querySelectorAll('.journey-section');
      if (sections && sections[index]) {
        // offsetTop is relative to the nearest positioned ancestor (the content wrapper).
        // Scrolling the scroll container to this value shows that section at viewport top.
        container.scrollTo({
          top: sections[index].offsetTop,
          behavior: 'smooth',
        });
      } else {
        // Fallback to proportional offset if section not yet in DOM
        const maxScroll = container.scrollHeight - container.clientHeight;
        container.scrollTo({ top: maxScroll * offset, behavior: 'smooth' });
      }
    } else {
      const sections = document.querySelectorAll('.journey-section');
      if (sections && sections[index]) {
        sections[index].scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  };

  const handleExit = () => {
    navigate('/user');
  };

  if (!visible) return null;

  return (
    <nav
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 50,
        display: 'flex',
        flexDirection: 'column',
        pointerEvents: 'none',
      }}
    >
      {/* Nav bar with solid background */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '1.25rem 2.5rem',
          background: '#050507',
          pointerEvents: 'auto',
        }}
      >
        {/* Wordmark */}
        <div
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '18px',
            fontWeight: 400,
            letterSpacing: '-0.02em',
            color: 'var(--ink-60)',
          }}
        >
          widTTS
        </div>

        {/* Section Navigation Labels */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '2rem',
          }}
          className="nav-labels"
        >
          {SECTIONS.map((section, i) => (
            <button
              key={section.id}
              onClick={() => handleJumpTo(i, section.offset)}
              style={{
                background: 'none',
                border: 'none',
                padding: '4px 0',
                cursor: 'pointer',
                fontFamily: 'var(--font-body)',
                fontSize: '11px',
                fontWeight: 500,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                color: currentSection === i ? 'var(--accent-bright)' : 'var(--ink-35)',
                transition: 'color 300ms cubic-bezier(0.16, 1, 0.3, 1)',
                position: 'relative',
              }}
              aria-label={`Jump to ${section.label} section`}
              onMouseEnter={(e) => {
                if (currentSection !== i) e.currentTarget.style.color = 'var(--ink-60)';
              }}
              onMouseLeave={(e) => {
                if (currentSection !== i) e.currentTarget.style.color = 'var(--ink-35)';
              }}
            >
              {section.label}
              {currentSection === i && (
                <span
                  style={{
                    position: 'absolute',
                    bottom: 0,
                    left: 0,
                    right: 0,
                    height: '1px',
                    background: 'var(--accent-bright)',
                    boxShadow: '0 0 8px var(--accent-mid)',
                  }}
                />
              )}
            </button>
          ))}

          <button
            onClick={handleExit}
            style={{
              background: 'none',
              border: 'none',
              padding: '4px 0',
              cursor: 'pointer',
              fontFamily: 'var(--font-body)',
              fontSize: '11px',
              fontWeight: 500,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: 'var(--ink-35)',
              transition: 'color 200ms',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--ink-100)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--ink-35)')}
          >
            Exit
          </button>
        </div>
      </div>

      {/* Fade-out gradient — from solid to transparent */}
      <div
        style={{
          height: '40px',
          background: 'linear-gradient(to bottom, #050507 0%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />
    </nav>
  );
}
