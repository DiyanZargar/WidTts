import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

/**
 * GlassComboBox — Searchable dropdown that allows custom text input.
 * Typing filters the list; pressing Enter or blurring accepts the typed value.
 * Selecting from the list works like a normal dropdown.
 */
export function GlassComboBox({ options = [], value, onChange, label, placeholder, disabled }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef(null);
  const panelRef = useRef(null);
  const inputRef = useRef(null);
  const [panelPos, setPanelPos] = useState({ top: 0, left: 0, width: 0 });

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target) && panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

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
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const selectedOption = options.find(o => o.value === value);
  const displayLabel = selectedOption ? selectedOption.label : value || '';

  const filtered = search.trim()
    ? options.filter(o => o.label.toLowerCase().includes(search.toLowerCase()) || o.value.toLowerCase().includes(search.toLowerCase()))
    : options;

  const handleSelect = (opt) => {
    onChange(opt.value);
    setOpen(false);
    setSearch('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && search.trim()) {
      // Use typed value as custom input
      onChange(search.trim());
      setOpen(false);
      setSearch('');
    }
    if (e.key === 'Escape') {
      setOpen(false);
      setSearch('');
    }
  };

  return (
    <div ref={ref} className="glass-dropdown">
      {label && <label className="type-micro" style={{ display: 'block', marginBottom: '4px', fontSize: '9px' }}>{label}</label>}
      <div
        onClick={() => open ? setOpen(false) : openPanel()}
        className={`glass-input glass-dropdown__trigger ${disabled ? 'glass-dropdown__trigger--disabled' : ''}`}
        style={disabled ? { opacity: 0.4, cursor: 'not-allowed' } : {}}
      >
        <span className={`glass-dropdown__trigger-text ${!displayLabel ? 'glass-dropdown__trigger-text--empty' : ''}`}>
          {displayLabel || placeholder || 'Select or type...'}
        </span>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, opacity: 0.4 }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {open && createPortal(
        <div
          ref={panelRef}
          className="glass-dropdown__panel"
          style={{ position: 'fixed', top: panelPos.top, left: panelPos.left, width: panelPos.width, maxHeight: '320px', overflowY: 'auto' }}
        >
          <div style={{ padding: '6px 8px', borderBottom: '1px solid rgba(255,255,255,0.08)', position: 'sticky', top: 0, background: '#111113', zIndex: 1 }}>
            <input
              ref={inputRef}
              className="glass-input"
              placeholder="Search or type custom name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleKeyDown}
              style={{ width: '100%', fontSize: '12px', padding: '6px 8px', boxSizing: 'border-box' }}
            />
          </div>
          {filtered.map((opt) => {
            const isSelected = value === opt.value;
            return (
              <div
                key={opt.value}
                className={`glass-dropdown__item ${isSelected ? 'glass-dropdown__item--selected' : ''}`}
                onClick={() => handleSelect(opt)}
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
          {search.trim() && !options.some(o => o.value === search.trim() || o.label.toLowerCase() === search.toLowerCase()) && (
            <div
              className="glass-dropdown__item"
              onClick={() => { onChange(search.trim()); setOpen(false); setSearch(''); }}
              style={{ color: 'var(--accent-bright)', borderTop: '1px solid rgba(255,255,255,0.08)' }}
            >
              <div className="glass-dropdown__radio" />
              <span className="glass-dropdown__label" style={{ color: 'var(--accent-bright)' }}>
                Use "{search.trim()}"
              </span>
            </div>
          )}
        </div>,
        document.body
      )}
    </div>
  );
}
