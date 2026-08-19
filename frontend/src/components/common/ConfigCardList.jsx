import { useState } from 'react';

/**
 * ConfigCardList — Reusable list of configured providers or bots.
 * Handles item selection, pagination (show more/less), edit/remove actions, and add-new trigger.
 */
export function ConfigCardList({
  title,
  count,
  items = [],
  visibleLimit = 3,
  selectedId,
  onSelect,
  onRemove,
  onAddNew,
  addNewLabel = 'Add New',
  renderSubtitle,
  renderBadge,
}) {
  const [showAll, setShowAll] = useState(false);
  const visibleItems = showAll ? items : items.slice(0, visibleLimit);

  if (!items || items.length === 0) return null;

  return (
    <div className="glass-pane mb-6 p-4 md:p-6">
      <div className="flex justify-between items-center mb-3">
        <span className="type-micro">
          {title} ({count ?? items.length})
        </span>
        {onAddNew && (
          <button
            type="button"
            onClick={onAddNew}
            className="bg-emerald-400 text-black text-xs font-semibold px-3.5 py-1.5 rounded-md flex items-center gap-1.5 hover:opacity-90 transition active:scale-95 cursor-pointer"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            {addNewLabel}
          </button>
        )}
      </div>

      <div className="flex flex-col gap-2">
        {visibleItems.map((item) => {
          const isSelected = selectedId === item.id;
          return (
            <div
              key={item.id}
              onClick={() => onSelect?.(item)}
              className={`flex items-center justify-between p-3.5 rounded-lg border cursor-pointer transition-all ${
                isSelected
                  ? 'bg-white/[0.06] border-emerald-400/80 shadow-[0_0_16px_rgba(0,0,0,0.5)]'
                  : 'bg-white/[0.02] border-white/[0.06] hover:border-white/20 hover:bg-white/[0.04]'
              }`}
            >
              <div className="flex items-center gap-3 min-w-0 pr-2">
                <span
                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 transition-colors ${
                    isSelected ? 'bg-emerald-400 shadow-[0_0_6px_var(--accent-bright)]' : 'bg-white/30'
                  }`}
                />
                <div className="min-w-0">
                  <div
                    className={`text-sm font-medium flex items-center gap-2 truncate ${
                      isSelected ? 'text-emerald-400' : 'text-white'
                    }`}
                  >
                    <span className="truncate">{item.name}</span>
                    {isSelected && (
                      <span className="text-[11px] text-white/60 font-normal flex-shrink-0">
                        (Editing)
                      </span>
                    )}
                    {renderBadge?.(item)}
                  </div>
                  {renderSubtitle && (
                    <div className="type-micro text-[10px] text-white/40 mt-0.5 truncate">
                      {renderSubtitle(item)}
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-3 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                <button
                  type="button"
                  onClick={() => onSelect?.(item)}
                  className="bg-white/5 border border-white/10 text-white/90 text-xs px-2.5 py-1 rounded hover:bg-white/10 transition"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => onRemove?.(item.id)}
                  className="text-xs text-white/35 hover:text-amber-500 transition px-1 py-1"
                >
                  Remove
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {items.length > visibleLimit && (
        <button
          type="button"
          onClick={() => setShowAll(!showAll)}
          className="w-full p-2 mt-2 border border-dashed border-white/10 rounded-md text-xs text-white/60 hover:text-emerald-400 hover:border-emerald-400/40 transition"
        >
          {showAll ? 'Show less' : `Show ${items.length - visibleLimit} more`}
        </button>
      )}
    </div>
  );
}
