import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

/**
 * GlassSelect — Custom single-select dropdown with radio-style indicators.
 * Same look as LanguageMultiSelect but with radio buttons instead of checkboxes.
 */
export function GlassSelect({ options = [], value, onChange, label, placeholder, disabled }) {
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
    if (disabled) return;
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      setPanelPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
    }
    setOpen(true);
  };

  const selectedOption = options.find(o => o.value === value);
  const displayText = selectedOption ? selectedOption.label : (placeholder || 'Select...');

  return (
    <div ref={ref} className="glass-dropdown">
      {label && <label className="type-micro" style={{ display: 'block', marginBottom: '4px', fontSize: '9px' }}>{label}</label>}
      <div
        onClick={() => open ? setOpen(false) : openPanel()}
        className={`glass-input glass-dropdown__trigger ${disabled ? 'glass-dropdown__trigger--disabled' : ''}`}
        style={disabled ? { opacity: 0.4, cursor: 'not-allowed' } : {}}
      >
        <span className={`glass-dropdown__trigger-text ${!selectedOption ? 'glass-dropdown__trigger-text--empty' : ''}`}>
          {displayText}
        </span>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, opacity: 0.4 }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {open && createPortal(
        <div
          ref={panelRef}
          className="glass-dropdown__panel"
          style={{ position: 'fixed', top: panelPos.top, left: panelPos.left, width: panelPos.width }}
        >
          {options.map((opt) => {
            const isSelected = value === opt.value;
            return (
              <div
                key={opt.value}
                className={`glass-dropdown__item ${isSelected ? 'glass-dropdown__item--selected' : ''}`}
                onClick={() => { onChange(opt.value); setOpen(false); }}
              >
                <div className={`glass-dropdown__radio ${isSelected ? 'glass-dropdown__radio--selected' : ''}`}>
                  {isSelected && <div className="glass-dropdown__radio-dot" />}
                </div>
                <span className={`glass-dropdown__label ${isSelected ? 'glass-dropdown__label--selected' : ''}`}>
                  {opt.label}
                </span>
              </div>
            );
          })}
        </div>,
        document.body
      )}
    </div>
  );
}
