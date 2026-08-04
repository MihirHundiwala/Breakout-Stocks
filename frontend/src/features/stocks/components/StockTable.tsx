import type { StockListItem } from "../types";
import type { WatchlistItem } from "../../watchlist/types";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router";
import { tradingViewUrl } from "../marketLinks";
import {
  formatAnalysisDate,
  formatPrice,
  formatSignedPercentage,
  movementClassName,
} from "../formatters";
import {
  FundamentalCoverageBadge,
  StockAnalysisStatusBadge,
} from "./StatusBadge";
import { MarketTermTooltip } from "./MarketTermTooltip";
import { SetupChartModal } from "./SetupChartModal";

function StockIdentity({ stock }: { stock: StockListItem }) {
  return (
    <div className="min-w-0">
      <p className="truncate font-semibold text-slate-950">
        {stock.companyName}
      </p>
      <p className="mt-1 truncate text-xs font-medium text-slate-500">
        {stock.exchange}:{stock.tradingSymbol}
      </p>
      <a
        href={tradingViewUrl(stock.exchange, stock.tradingSymbol)}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        aria-label={`Open ${stock.companyName} chart on TradingView in a new tab`}
      >
        View chart <span aria-hidden="true">↗</span>
      </a>
    </div>
  );
}

function FundamentalStatusLink({ stock }: { stock: StockListItem }) {
  const hasAnalysisDetail = stock.technicalStatus !== null;
  return (
    <div className="flex items-center gap-1.5">
      <FundamentalCoverageBadge status={stock.fundamentalCoverage} />
      {hasAnalysisDetail && (
        <Link
          to={`/stocks/${stock.instrumentId}`}
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-blue-700 ring-1 ring-inset ring-blue-200 transition hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          aria-label={`Open fundamental research for ${stock.companyName}`}
          title="Open fundamental research"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
            <path d="m7.5 4.5 5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Link>
      )}
    </div>
  );
}


function CloseValue({
  stock,
  watchlistItem,
}: {
  stock: StockListItem;
  watchlistItem: WatchlistItem | undefined;
}) {
  if (stock.closePrice === null) {
    return (
      <div>
        <p className="font-semibold text-slate-500">—</p>
        <p className="mt-1 text-xs font-medium text-slate-500">
          Analysis unavailable
        </p>
      </div>
    );
  }

  return (
    <div className="tabular-nums">
      <p className="font-semibold text-slate-950">
        {formatPrice(stock.closePrice)}
      </p>
      <p
        className={`mt-1 text-xs font-medium ${movementClassName(stock.dayChangePercent)}`}
      >
        1 day: {formatSignedPercentage(stock.dayChangePercent)}
      </p>
      <p
        className={`mt-1 text-xs font-semibold ${movementClassName(watchlistItem?.movementSinceAddedPercent ?? "0")}`}
      >
        Since added: {watchlistItem === undefined
          ? "Not in personal watchlist"
          : watchlistItem.movementSinceAddedPercent === null
            ? "Awaiting price history"
            : formatSignedPercentage(watchlistItem.movementSinceAddedPercent)}
      </p>
    </div>
  );
}

function marketDataSource(source: string | null): string {
  if (source === null) return "Unavailable";
  if (source.toUpperCase() === "UPSTOX") return "Upstox";
  if (source.toUpperCase() === "FIXTURE") return "Demo market data";
  return "Market data";
}

function formatMarketCap(value: string | null): string {
  if (value === null) return "Unknown";
  return `₹${new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
  }).format(Number(value))} cr`;
}

export function StockActionsMenu({
  companyName,
  globalDelete,
  removing,
  onRemove,
}: {
  companyName: string;
  globalDelete: boolean;
  removing: boolean;
  onRemove: () => void;
}) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });

  function positionMenu() {
    const button = buttonRef.current;
    if (!button) return;
    const rect = button.getBoundingClientRect();
    const menuWidth = 208;
    const menuHeight = 52;
    const gap = 6;
    const viewportPadding = 8;
    const openAbove = window.innerHeight - rect.bottom < menuHeight + gap;

    setMenuPosition({
      top: openAbove
        ? Math.max(viewportPadding, rect.top - menuHeight - gap)
        : Math.min(window.innerHeight - menuHeight - viewportPadding, rect.bottom + gap),
      left: Math.min(
        window.innerWidth - menuWidth - viewportPadding,
        Math.max(viewportPadding, rect.right - menuWidth),
      ),
    });
  }

  useEffect(() => {
    if (!open) return;
    function closeOnOutsideClick(event: PointerEvent) {
      const target = event.target as Node;
      if (!buttonRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        setOpen(false);
      }
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    window.addEventListener("resize", positionMenu);
    window.addEventListener("scroll", positionMenu, true);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("resize", positionMenu);
      window.removeEventListener("scroll", positionMenu, true);
    };
  }, [open]);

  return (
    <div>
      <button
        ref={buttonRef}
        type="button"
        aria-label={`Actions for ${companyName}`}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={removing}
        onClick={() => {
          if (!open) positionMenu();
          setOpen((value) => !value);
        }}
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-xl leading-none text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-blue-600 disabled:opacity-50"
      >
        {removing ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-blue-600" aria-label="Removing" />
        ) : (
          <span aria-hidden="true">⋮</span>
        )}
      </button>
      {open && createPortal(
        <div
          ref={menuRef}
          role="menu"
          style={{ top: menuPosition.top, left: menuPosition.left }}
          className="fixed z-50 w-52 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl shadow-slate-200/70"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onRemove();
            }}
            className="w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-red-700 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-red-600"
          >
            {globalDelete ? "Delete company data" : "Remove from watchlist"}
          </button>
        </div>,
        document.body,
      )}
    </div>
  );
}

export function StockTable({
  items,
  watchlistItemsByInstrument,
  removingInstrumentId,
  onRemove,
  globalDelete,
}: {
  items: StockListItem[];
  watchlistItemsByInstrument: ReadonlyMap<number, WatchlistItem>;
  removingInstrumentId: number | null;
  onRemove: (stock: StockListItem) => void;
  globalDelete: boolean;
}) {
  const [chartStock, setChartStock] = useState<StockListItem | null>(null);

  function StatusWithChart({ stock }: { stock: StockListItem }) {
    const chartAvailable =
      stock.operationalState !== "ANALYSIS_FAILED"
      && stock.hasChartData
      && stock.technicalStatus !== null
      && stock.technicalStatus !== "NO_SETUP";
    return (
      <div className="flex items-center gap-1.5">
        <StockAnalysisStatusBadge
          status={stock.technicalStatus}
          operationalState={stock.operationalState}
          errorCode={stock.analysisErrorCode}
        />
        {chartAvailable && (
          <button
            type="button"
            onClick={() => setChartStock(stock)}
            className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-blue-700 ring-1 ring-inset ring-blue-200 transition hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            aria-label={`Inspect setup chart for ${stock.companyName}`}
            title="Inspect setup chart"
          >
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
              <path d="m7.5 4.5 5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>
    );
  }

  return (
    <>
      <div className="hidden overflow-x-auto border-t border-slate-100 lg:block">
        <table className="w-full min-w-[940px] divide-y divide-slate-200 text-left">
          <caption className="sr-only">
            Latest setup research for each stock
          </caption>
          <thead className="bg-slate-50">
            <tr>
              <th
                scope="col"
                className="px-6 py-3 text-xs font-semibold tracking-wide text-slate-500 uppercase"
              >
                Name
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-xs font-semibold tracking-wide text-slate-500 uppercase"
              >
                Market cap
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-xs font-semibold tracking-wide text-slate-500 uppercase"
              >
                <span className="inline-flex items-center whitespace-nowrap">
                  Latest close
                  <MarketTermTooltip label="latest close">
                    The latest completed-session close, its one-day move, and the percentage move from the close recorded when you most recently added this stock.
                  </MarketTermTooltip>
                </span>
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-xs font-semibold tracking-wide text-slate-500 uppercase"
              >
                As of
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-xs font-semibold tracking-wide text-slate-500 uppercase"
              >
                Technical status
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-xs font-semibold tracking-wide text-slate-500 uppercase"
              >
                Fundamental status
              </th>
              <th scope="col" className="w-14 px-3 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {items.map((stock) => (
              <tr key={stock.instrumentId}>
                <td className="px-6 py-5 align-top">
                  <StockIdentity stock={stock} />
                </td>
                <td className="px-6 py-5 align-top text-sm font-medium whitespace-nowrap text-slate-900 tabular-nums">
                  {formatMarketCap(stock.marketCapCrore)}
                </td>
                <td className="px-6 py-5 align-top">
                  <CloseValue stock={stock} watchlistItem={watchlistItemsByInstrument.get(stock.instrumentId)} />
                </td>
                <td className="px-6 py-5 align-top">
                  {stock.operationalState === "ANALYSIS_FAILED" ? (
                    <>
                      <p className="whitespace-nowrap text-sm font-medium text-slate-900">
                        Failed for {formatAnalysisDate(stock.analysisErrorSession)}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">Analysis unavailable</p>
                    </>
                  ) : (
                    <>
                      <p className="whitespace-nowrap text-sm font-medium text-slate-900">
                        {formatAnalysisDate(stock.analysisDate)}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Market data: {marketDataSource(stock.source)}
                      </p>
                    </>
                  )}
                </td>
                <td className="px-6 py-5 align-top">
                  <StatusWithChart stock={stock} />
                </td>
                <td className="px-6 py-5 align-top">
                  <FundamentalStatusLink stock={stock} />
                </td>
                <td className="px-3 py-4 text-right align-top">
                  {(globalDelete || watchlistItemsByInstrument.has(stock.instrumentId)) && (
                    <StockActionsMenu
                      companyName={stock.companyName}
                      globalDelete={globalDelete}
                      removing={removingInstrumentId === stock.instrumentId}
                      onRemove={() => onRemove(stock)}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 border-t border-slate-100 p-3 sm:p-4 lg:hidden">
        {items.map((stock) => (
          <article
            key={stock.instrumentId}
            className="min-w-0 rounded-xl border border-slate-200 p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <StockIdentity stock={stock} />
              <div className="shrink-0">
                {(globalDelete || watchlistItemsByInstrument.has(stock.instrumentId)) && (
                  <StockActionsMenu
                    companyName={stock.companyName}
                    globalDelete={globalDelete}
                    removing={removingInstrumentId === stock.instrumentId}
                    onRemove={() => onRemove(stock)}
                  />
                )}
              </div>
            </div>
            <p className="mt-3 text-xs font-medium text-slate-500">
              {stock.operationalState === "ANALYSIS_FAILED" ? (
                <>Failed for {formatAnalysisDate(stock.analysisErrorSession)}</>
              ) : (
                <>
                  As of {formatAnalysisDate(stock.analysisDate)}
                  <span aria-hidden="true"> / </span>
                  {marketDataSource(stock.source)}
                </>
              )}
            </p>
            <dl className="mt-4 grid grid-cols-2 gap-2.5">
              <div className="rounded-xl bg-slate-50 p-3">
                <dt className="text-xs font-medium text-slate-500">Market cap</dt>
                <dd className="mt-1.5 text-sm font-semibold text-slate-950 tabular-nums">
                  {formatMarketCap(stock.marketCapCrore)}
                </dd>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <dt className="text-xs font-medium text-slate-500">
                  Latest close
                  <MarketTermTooltip label="latest close">
                    The latest close, one-day move, and percentage move since you most recently added this stock. Removing and re-adding resets that baseline.
                  </MarketTermTooltip>
                </dt>
                <dd className="mt-1.5">
                  <CloseValue stock={stock} watchlistItem={watchlistItemsByInstrument.get(stock.instrumentId)} />
                </dd>
              </div>
            </dl>
            <dl className="mt-3 divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white px-3">
              <div className="flex items-center justify-between gap-3 py-3">
                <dt className="text-xs font-medium text-slate-500">Technical status</dt>
                <dd className="min-w-0"><StatusWithChart stock={stock} /></dd>
              </div>
              <div className="flex items-center justify-between gap-3 py-3">
                <dt className="text-xs font-medium text-slate-500">Fundamental status</dt>
                <dd className="min-w-0"><FundamentalStatusLink stock={stock} /></dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
      {chartStock && (
        <SetupChartModal
          stock={chartStock}
          onClose={() => setChartStock(null)}
        />
      )}
    </>
  );
}
