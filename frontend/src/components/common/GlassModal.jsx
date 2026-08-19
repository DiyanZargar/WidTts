import { useEffect } from 'react';
import { createPortal } from 'react-dom';

/**
 * GlassModal — Standardized glassmorphism modal with portal rendering and ESC key dismissal.
 */
export function GlassModal({ open, title, children, onClose, footer, maxWidth = 'max-w-md' }) {
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose?.();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[1000] bg-black/75 backdrop-blur-md flex items-center justify-center p-6 animate-[halo-fade-in_200ms_ease-out]"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={typeof title === 'string' ? title : 'Modal Dialog'}
    >
      <div
        className={`w-full ${maxWidth} bg-[#0f0f13] border border-white/15 rounded-2xl p-7 shadow-2xl animate-[halo-modal-pop_240ms_cubic-bezier(0.16,1,0.3,1)]`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white tracking-tight">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="text-white/40 hover:text-white text-lg w-7 h-7 rounded-full flex items-center justify-center hover:bg-white/10 transition"
          >
            ✕
          </button>
        </div>

        <div className="text-sm text-white/70 leading-relaxed mb-6">{children}</div>

        {footer && (
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/10">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
