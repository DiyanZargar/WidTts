/**
 * OverviewSection — First section of the journey.
 * Wordmark headline, one line description.
 * No boxes, just type floating on void.
 */
export function OverviewSection() {
  return (
    <div className="journey-section" style={{ minHeight: '100vh', alignItems: 'center' }}>
      <div style={{ textAlign: 'center', maxWidth: '800px', width: '100%' }}>
        <h2
          className="type-display type-display-xl"
          style={{ marginBottom: '1.5rem' }}
        >
          Voice Platform
        </h2>
        <p
          className="type-body"
          style={{
            fontSize: '17px',
            lineHeight: 1.7,
            maxWidth: '520px',
            margin: '0 auto 2rem',
          }}
        >
          Configure your AI voice bot in one continuous journey.
          Connect an LLM, choose a speech provider, define its personality — and launch.
        </p>
      </div>
    </div>
  );
}
