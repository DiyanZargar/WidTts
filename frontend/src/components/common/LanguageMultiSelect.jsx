import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

/**
 * LanguageMultiSelect — Compact dropdown for selecting multiple languages with a primary indicator.
 * Clicking the dropdown opens a checklist. ★ marks the primary language.
 */
export function LanguageMultiSelect({ languages = [], selected = [], primary, onChange, onSetPrimary, label }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const panelRef = useRef(null);
  const [panelPos, setPanelPos] = useState({ top: 0, left: 0, width: 0 });

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target) && panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Keep panel position synced on scroll/resize
  useEffect(() => {
    if (!open) return;
    const updatePos = () => {
      if (ref.current) {
        const rect = ref.current.getBoundingClientRect();
        setPanelPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
    };
    window.addEventListener('scroll', updatePos, true);
    window.addEventListener('resize', updatePos);
    return () => { window.removeEventListener('scroll', updatePos, true); window.removeEventListener('resize', updatePos); };
  }, [open]);

  const openPanel = () => {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      setPanelPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
    }
    setOpen(true);
  };

  const langs = languages.length > 0 ? languages : [{ code: 'en', name: 'English' }];
  const displayText = selected.length === 0
    ? 'None'
    : selected.length === 1
      ? langs.find(l => l.code === selected[0])?.name || selected[0]
      : `${langs.find(l => l.code === primary)?.name || primary} +${selected.length - 1}`;

  const toggle = (code) => {
    const next = selected.includes(code)
      ? selected.filter(c => c !== code)
      : [...selected, code];
    if (next.length === 0) return;
    onChange(next);
  };

  return (
    <div ref={ref} className="lang-dropdown">
      <label className="type-micro" style={{ display: 'block', marginBottom: '4px', fontSize: '9px' }}>{label}</label>
      <div
        onClick={() => open ? setOpen(false) : openPanel()}
        className="glass-input lang-dropdown__trigger"
      >
        <span className={`lang-dropdown__trigger-text ${selected.length === 0 ? 'lang-dropdown__trigger-text--empty' : ''}`}>
          {displayText}
        </span>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, opacity: 0.4 }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {open && createPortal(
        <div
          ref={panelRef}
          className="lang-dropdown__panel"
          style={{ position: 'fixed', top: panelPos.top, left: panelPos.left, width: panelPos.width }}
        >
          {langs.map((lang) => {
            const isSelected = selected.includes(lang.code);
            const isPrimary = primary === lang.code;
            return (
              <div
                key={lang.code}
                className={`lang-dropdown__item ${isSelected ? 'lang-dropdown__item--selected' : ''}`}
              >
                <div
                  onClick={() => toggle(lang.code)}
                  className={`lang-dropdown__checkbox ${isSelected ? 'lang-dropdown__checkbox--checked' : ''}`}
                >
                  {isSelected && (
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                </div>
                <span
                  onClick={() => toggle(lang.code)}
                  className={`lang-dropdown__label ${isSelected ? 'lang-dropdown__label--selected' : ''}`}
                >
                  {lang.name}
                </span>
                {isSelected && (
                  <span
                    onClick={(e) => { e.stopPropagation(); onSetPrimary(lang.code); }}
                    title="Set as primary"
                    className={`lang-dropdown__star ${isPrimary ? 'lang-dropdown__star--primary' : ''}`}
                  >
                    {isPrimary ? '★' : '☆'}
                  </span>
                )}
              </div>
            );
          })}
        </div>,
        document.body
      )}
    </div>
  );
}
