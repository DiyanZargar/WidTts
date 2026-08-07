import { useNavigate } from 'react-router-dom';

const SECTIONS = [
  { id: 'overview', label: 'Overview', offset: 0 },
  { id: 'llm', label: 'LLM', offset: 0.143 },
  { id: 'realtime', label: 'Realtime', offset: 0.286 },
  { id: 'speech', label: 'Speech', offset: 0.428 },
  { id: 'bot', label: 'Bot', offset: 0.571 },
  { id: 'activate', label: 'Activate', offset: 0.714 },
  { id: 'live', label: 'Live', offset: 0.857 },
];

/**
 * TopNav — Fixed transparent nav with 3D + 2D scroll-spy sync.
 * Clicking any section label smoothly scrolls BOTH the 3D camera/orb and HTML section.
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
      const maxScroll = container.scrollHeight - container.clientHeight;
      container.scrollTo({
        top: maxScroll * offset,
        behavior: 'smooth',
      });
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
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '1.25rem 2.5rem',
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
    </nav>
  );
}
