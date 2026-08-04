import { useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function MarketTermTooltip({
  label,
  children,
}: {
  label: string;
  children: string;
}) {
  const tooltipId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  function showTooltip() {
    const button = buttonRef.current;
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const tooltipWidth = 224;
    const estimatedHeight = 88;
    const viewportPadding = 8;
    const gap = 8;
    const left = Math.min(
      window.innerWidth - tooltipWidth - viewportPadding,
      Math.max(viewportPadding, rect.left + rect.width / 2 - tooltipWidth / 2),
    );
    setPosition({
      top: rect.top >= estimatedHeight + gap
        ? rect.top - estimatedHeight - gap
        : rect.bottom + gap,
      left,
    });
  }

  return (
    <span className="inline-flex align-middle">
      <button
        ref={buttonRef}
        type="button"
        aria-label={`About ${label}`}
        aria-describedby={tooltipId}
        onMouseEnter={showTooltip}
        onMouseLeave={() => setPosition(null)}
        onFocus={showTooltip}
        onBlur={() => setPosition(null)}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-slate-400 text-[10px] font-bold normal-case text-slate-500 hover:border-blue-600 hover:text-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        i
      </button>
      {position && createPortal(
        <span
          id={tooltipId}
          role="tooltip"
          style={position}
          className="pointer-events-none fixed z-[60] w-56 rounded-lg bg-slate-950 px-3 py-2 text-left text-xs font-normal leading-5 tracking-normal text-white normal-case shadow-xl"
        >
          {children}
        </span>,
        document.body,
      )}
    </span>
  );
}
