import { useState, useEffect, useRef, useCallback } from 'react';
import { Canvas } from '@react-three/fiber';
import { ScrollControls, Scroll, useScroll } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { EntryGate } from './EntryGate';
import { TopNav } from './TopNav';
import { ScrollMouseIndicator } from './ScrollMouseIndicator';
import { ParticleVoid } from './ParticleVoid';
import { CoreSphere } from './CoreSphere';
import { CameraRig } from './CameraRig';
import { OverviewSection } from './sections/OverviewSection';
import { LLMSection } from './sections/LLMSection';
import { SpeechSection } from './sections/SpeechSection';
import { BotIdentitySection } from './sections/BotIdentitySection';
import { ReviewSection } from './sections/ReviewSection';
import { DeploySection } from './sections/DeploySection';
import { LiveSection } from './sections/LiveSection';

/**
 * Initial scroll pages — must be large enough so the fill div lets users
 * scroll to all sections even before ScrollPagesMeter corrects it.
 * 7.3 = 6 sections × 100vh + 1.3 buffer, matching TopNav Live offset 0.833 = 5/6.
 */
const SCROLL_PAGES = 7.3;

/**
 * ScrollPagesMeter — Runs INSIDE the Canvas on every animation frame.
 *
 * WHY THIS EXISTS:
 * drei's ScrollControls captures `scrollThreshold` ONCE on mount in a closure.
 * If HTML sections later grow taller than 100vh (BotIdentity=1314 lines,
 * LLM=664 lines), the Live section drifts past the stale threshold.
 *
 * Previous React-state approach caused drei's useEffect (pages in its deps)
 * to re-run and reset el.scrollTop = 1 — teleporting user back to top.
 *
 * This component bypasses React state entirely:
 * 1. Measures actual content height from the DOM wrapper every frame.
 * 2. Updates data.fill.style.height (scrollable spacer) directly.
 * 3. Updates data.pages (used in translation formula) directly.
 * 4. Corrects data.scroll.current using ACTUAL threshold (not drei's stale one).
 * 5. Applies the corrected CSS transform directly, bypassing delta > eps guard.
 *
 * No re-renders. No scroll resets. Smooth every frame.
 */
function ScrollPagesMeter() {
  const data = useScroll();
  const smoothRef = useRef(0);

  useFrame(() => {
    // The HTML content wrapper = first child of drei's sticky viewport div
    const wrapper = data.fixed && data.fixed.firstElementChild;
    if (!wrapper) return;

    const contentH = wrapper.scrollHeight;
    const viewportH = window.innerHeight;
    if (!contentH || !viewportH) return;

    // pages = viewport-heights in content (no buffer — last section visible at max scroll)
    const correctPages = contentH / viewportH;

    // Update fill height so max scrollTop covers all content
    if (Math.abs(correctPages - data.pages) > 0.05) {
      data.fill.style.height = correctPages * 100 + '%';
      data.pages = correctPages;
    }

    // Correct raw offset using ACTUAL content height (not drei's stale captured threshold)
    const correctThreshold = contentH - viewportH;
    const rawOffset = correctThreshold > 0 ? data.el.scrollTop / correctThreshold : 0;

    // Smooth the corrected offset (matches drei's 0.15 damping)
    smoothRef.current += (rawOffset - smoothRef.current) * (data.damping || 0.15);

    // Apply corrected translation, overriding drei's stale one
    const translate = viewportH * (data.pages - 1) * -smoothRef.current;
    wrapper.style.transform = 'translate3d(0,' + translate + 'px,0)';

    // Keep data.scroll.current in sync so drei's damping also converges
    data.scroll.current = rawOffset;
  });

  return null;
}

/**
 * ScrollTracker — Internal component that reads useScroll() inside Canvas context
 * and calls back with offset/section for the outer TopNav.
 */
function ScrollTracker({ onScroll }) {
  const scroll = useScroll();

  const frameRef = useRef(0);
  useEffect(() => {
    let running = true;
    const tick = () => {
      if (!running) return;
      if (scroll) {
        const offset = scroll.offset;
        const section = Math.min(5, Math.floor(offset * 6));
        onScroll(offset, section);
      }
      frameRef.current = requestAnimationFrame(tick);
    };
    tick();
    return () => { running = false; cancelAnimationFrame(frameRef.current); };
  }, [scroll, onScroll]);

  return null;
}

/**
 * CorePositioned — Positions the Core sphere along the camera path so it's
 * visible at different scroll depths.
 */
function CorePositioned({ progress, activated }) {
  const scroll = useScroll();
  const ref = useRef();

  useEffect(() => {
    let running = true;
    const tick = () => {
      if (!running) return;
      if (ref.current && scroll) {
        const y = -scroll.offset * 40;
        ref.current.position.y += (y - ref.current.position.y) * 0.05;
      }
      requestAnimationFrame(tick);
    };
    tick();
    return () => { running = false; };
  }, [scroll]);

  return (
    <group ref={ref}>
      <CoreSphere progress={progress} activated={activated} />
    </group>
  );
}

/**
 * ScrollGlow — A radial glow that follows the user's scroll position.
 */
function ScrollGlow({ scrollOffset }) {
  const topPercent = 30 + scrollOffset * 40;
  return (
    <div className="scroll-glow" style={{ top: topPercent + '%' }} />
  );
}

/**
 * Find the ScrollControls scroll container — the div with overflowY: auto
 * that ScrollControls creates as a sibling of the canvas.
 */
function findScrollContainer() {
  const candidates = document.querySelectorAll('div');
  for (const el of candidates) {
    const style = window.getComputedStyle(el);
    if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight) {
      return el;
    }
  }
  return null;
}

/**
 * AdminJourney — Main orchestrator.
 * One route, one Canvas, one scrollbar.
 * Composed of: EntryGate → Canvas (3D) + ScrollControls (HTML sections).
 */
export function AdminJourney() {
  const [gateOpen, setGateOpen] = useState(true);
  const [currentSection, setCurrentSection] = useState(0);
  const [scrollOffset, setScrollOffset] = useState(0);
  const [setupProgress, setSetupProgress] = useState(0);
  const [activated, setActivated] = useState(false);
  const scrollRef = useRef();
  const [highlightBotId, setHighlightBotId] = useState(null);

  // Provider state for passing to BotIdentitySection
  const [llmProviders, setLlmProviders] = useState([]);
  const [speechProviders, setSpeechProviders] = useState([]);
  const [botRefreshTrigger, setBotRefreshTrigger] = useState(0);

  // Load providers on mount
  useEffect(() => {
    fetch('/admin/api/llm-providers').then(r => r.json()).then(setLlmProviders).catch(() => {});
    fetch('/admin/api/speech-providers').then(r => r.json()).then(setSpeechProviders).catch(() => {});
  }, []);

  // Check if already authed
  useEffect(() => {
    const role = sessionStorage.getItem('widtts_role');
    if (role === 'admin') setGateOpen(false);
  }, []);

  const handleEnterAdmin = useCallback(() => {
    setGateOpen(false);
  }, []);

  const handleScroll = useCallback((offset, section) => {
    setCurrentSection(section);
    setScrollOffset(offset);
  }, []);

  const handleLLMCreated = useCallback((data) => {
    setSetupProgress(p => Math.max(p, 0.25));
    fetch('/admin/api/llm-providers').then(r => r.json()).then(setLlmProviders).catch(() => {});
  }, []);

  const handleSpeechCreated = useCallback((data) => {
    setSetupProgress(p => Math.max(p, 0.75));
    fetch('/admin/api/speech-providers').then(r => r.json()).then(setSpeechProviders).catch(() => {});
  }, []);

  const handleBotCreated = useCallback((data) => {
    setBotRefreshTrigger(t => t + 1);
  }, []);

  const handleActivated = useCallback(() => {
    setActivated(true);
  }, []);

  // No-op: ScrollPagesMeter handles resizing automatically every frame
  const handleExtraPages = useCallback(() => {}, []);

  /**
   * Navigate to Deploy section and scroll to a specific bot card.
   */
  const handleNavigateToDeploy = useCallback((botId) => {
    setHighlightBotId(botId || null);
    setTimeout(() => {
      const container = findScrollContainer();
      if (!container || !botId) return;
      const card = document.querySelector('[data-bot-id="' + botId + '"]');
      if (!card) return;
      const cardRelativeTop = card.offsetTop - container.offsetTop;
      container.scrollTo({ top: cardRelativeTop - 60, behavior: 'smooth' });
    }, 300);
  }, []);

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      {/* Entry Password Gate */}
      <EntryGate open={gateOpen} onAuthenticated={handleEnterAdmin} />

      {/* Top Navigation */}
      <TopNav scrollRef={scrollRef} currentSection={currentSection} visible={!gateOpen} />

      {/* Dynamic Scroll Mouse Indicator */}
      {!gateOpen && (
        <ScrollMouseIndicator
          scrollRef={scrollRef}
          currentSection={currentSection}
          scrollOffset={scrollOffset}
        />
      )}

      {/* Viewport Border Effect */}
      <div className="viewport-border viewport-border--top" />
      <div className="viewport-border viewport-border--bottom" />
      <div className="viewport-border viewport-border--left" />
      <div className="viewport-border viewport-border--right" />

      {/* Scroll Spotlight Glow */}
      <ScrollGlow scrollOffset={scrollOffset} />

      {/* Main 3D Canvas + Scroll Experience */}
      <div style={{ width: '100%', height: '100%', pointerEvents: 'auto' }}>
        <Canvas
          camera={{ position: [0, 0, 8], fov: 45 }}
          gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
          style={{ background: '#050507' }}
        >
          <color attach="background" args={['#050507']} />
          <ambientLight intensity={0.15} />
          <directionalLight position={[5, 10, 5]} intensity={0.4} color="hsl(155, 95%, 58%)" />
          <pointLight position={[-5, 5, -5]} intensity={0.3} color="hsl(160, 90%, 42%)" />
          <pointLight position={[4, -20, 2]} intensity={0.5} color="hsl(155, 95%, 58%)" />
          <pointLight position={[0, -40, 3]} intensity={0.4} color="hsl(160, 90%, 42%)" />

          <ScrollControls pages={SCROLL_PAGES} damping={0.15}>
            {/* 3D content layer */}
            <Scroll>
              <CameraRig />
              <CorePositioned progress={setupProgress} activated={activated} />
              <ParticleVoid />
            </Scroll>

            {/* HTML content layer — moves with scroll */}
            <Scroll html style={{ width: '100%' }}>
              <div style={{ width: '100%', position: 'relative' }}>
                <OverviewSection />
                <LLMSection onProviderCreated={handleLLMCreated} />
                <SpeechSection onProviderCreated={handleSpeechCreated} />
                <BotIdentitySection
                  llmProviders={llmProviders}
                  speechProviders={speechProviders}
                  onBotCreated={handleBotCreated}
                  onNavigateToDeploy={handleNavigateToDeploy}
                />
                <DeploySection
                  onActivated={handleActivated}
                  refreshTrigger={botRefreshTrigger}
                  highlightBotId={highlightBotId}
                  onExtraPages={handleExtraPages}
                />
                <LiveSection />
              </div>
            </Scroll>

            {/* Scroll tracker for nav sync */}
            <ScrollTracker onScroll={handleScroll} />

            {/*
              Corrects drei's stale scrollThreshold every frame.
              No React state. No scroll position resets.
            */}
            <ScrollPagesMeter />
          </ScrollControls>
        </Canvas>
      </div>
    </div>
  );
}
