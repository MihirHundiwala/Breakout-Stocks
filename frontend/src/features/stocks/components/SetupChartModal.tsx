import { useEffect, useId, useRef, useState } from "react";

import { useStockChart } from "../hooks/useStockChart";
import type { AnalysisChartData, StockListItem } from "../types";
import { TechnicalStatusBadge } from "./StatusBadge";


const WIDTH = 820;
const HEIGHT = 430;
const LEFT = 68;
const RIGHT = 22;
const TOP = 24;
const PRICE_BOTTOM = 326;
const VOLUME_TOP = 350;
const VOLUME_BOTTOM = 400;

function shortDate(value: string, timeframe: "DAILY" | "WEEKLY"): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    ...(timeframe === "WEEKLY" ? { year: "numeric" } : {}),
  }).format(new Date(`${value}T00:00:00`));
}

function priceLabel(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function signedPercentage(value: number): string {
  const normalized = Math.abs(value) < 0.005 ? 0 : value;
  return `${normalized > 0 ? "+" : ""}${normalized.toFixed(2)}%`;
}

function latestPriceSummary(data: AnalysisChartData | null) {
  if (!data || data.candles.length < 2) return null;
  const latestClose = Number(data.candles.at(-1)?.close);
  const previousClose = Number(data.candles.at(-2)?.close);
  if (
    !Number.isFinite(latestClose)
    || !Number.isFinite(previousClose)
    || previousClose <= 0
  ) {
    return null;
  }
  return {
    latestClose,
    changePercent: ((latestClose / previousClose) - 1) * 100,
    periodLabel: data.timeframe === "WEEKLY" ? "This week" : "1-day",
  };
}

function SetupCandlestickChart({ data, companyName }: { data: AnalysisChartData; companyName: string }) {
  const parsed = data.candles.map((item) => ({
    ...item,
    openValue: Number(item.open),
    highValue: Number(item.high),
    lowValue: Number(item.low),
    closeValue: Number(item.close),
  }));
  const zoneLower = Number(data.resistanceZoneLower);
  const zoneUpper = Number(data.resistanceZoneUpper);
  const breakoutThreshold = Number(data.resistanceZoneUpper);
  const rawMinimum = Math.min(zoneLower, ...parsed.map((item) => item.lowValue));
  const rawMaximum = Math.max(zoneUpper, ...parsed.map((item) => item.highValue));
  const visibleRange = Math.max(rawMaximum - rawMinimum, rawMaximum * 0.01);
  const minimum = rawMinimum - visibleRange * 0.08;
  const maximum = rawMaximum + visibleRange * 0.08;
  const plotWidth = WIDTH - LEFT - RIGHT;
  const candleStep = plotWidth / parsed.length;
  const bodyWidth = Math.max(2, Math.min(8, candleStep * 0.62));
  const maximumVolume = Math.max(1, ...parsed.map((item) => item.volume));
  const touchDates = new Set(data.resistanceTouchDates);
  const y = (value: number) =>
    TOP + ((maximum - value) / (maximum - minimum)) * (PRICE_BOTTOM - TOP);
  const x = (index: number) => LEFT + candleStep * (index + 0.5);
  const yTicks = Array.from({ length: 5 }, (_, index) =>
    maximum - ((maximum - minimum) * index) / 4,
  );
  const xTickIndexes = Array.from(
    new Set([0, Math.floor((parsed.length - 1) / 3), Math.floor((parsed.length - 1) * 2 / 3), parsed.length - 1]),
  );

  return (
    <div className="w-full overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 p-1.5 sm:p-3">
      <svg
        role="img"
        aria-label={`${companyName} ${data.timeframe.toLowerCase()} setup candlestick chart from ${data.candles[0].date} to ${data.candles.at(-1)?.date}`}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="block h-auto w-full"
      >
        <rect x={LEFT} y={TOP} width={plotWidth} height={PRICE_BOTTOM - TOP} fill="white" />
        <text
          x="14"
          y={(TOP + PRICE_BOTTOM) / 2}
          textAnchor="middle"
          fontSize="12"
          fontWeight="600"
          fill="#334155"
          transform={`rotate(-90 14 ${(TOP + PRICE_BOTTOM) / 2})`}
        >
          Price (₹)
        </text>
        {yTicks.map((tick) => (
          <g key={tick}>
            <line x1={LEFT} x2={WIDTH - RIGHT} y1={y(tick)} y2={y(tick)} stroke="#e2e8f0" strokeWidth="1" />
            <text x={LEFT - 8} y={y(tick) + 4} textAnchor="end" fontSize="11" fontWeight="600" fill="#475569">
              {priceLabel(tick)}
            </text>
          </g>
        ))}
        <rect
          data-chart-role="resistance-zone"
          x={LEFT}
          y={y(zoneUpper)}
          width={plotWidth}
          height={Math.max(2, y(zoneLower) - y(zoneUpper))}
          fill="#f59e0b"
          fillOpacity="0.16"
        />
        <line
          data-chart-role="breakout-threshold"
          x1={LEFT}
          x2={WIDTH - RIGHT}
          y1={y(breakoutThreshold)}
          y2={y(breakoutThreshold)}
          stroke="#d97706"
          strokeDasharray="6 4"
          strokeWidth="1.5"
        />
        {parsed.map((item, index) => {
          const bullish = item.closeValue >= item.openValue;
          const color = bullish ? "#059669" : "#dc2626";
          const bodyTop = y(Math.max(item.openValue, item.closeValue));
          const bodyBottom = y(Math.min(item.openValue, item.closeValue));
          const touchPrice = Math.max(
            zoneLower,
            Math.min(breakoutThreshold, item.highValue),
          );
          const confirmedZoneTouch = (
            touchDates.has(item.date)
            && item.highValue >= zoneLower
            && item.lowValue <= zoneUpper
          );
          return (
            <g key={item.date}>
              <line
                data-chart-role="candle-wick"
                data-date={item.date}
                x1={x(index)}
                x2={x(index)}
                y1={y(item.highValue)}
                y2={y(item.lowValue)}
                stroke={color}
                strokeWidth="1"
              />
              <rect
                x={x(index) - bodyWidth / 2}
                y={bodyTop}
                width={bodyWidth}
                height={Math.max(1.5, bodyBottom - bodyTop)}
                fill={color}
                rx="0.5"
              />
              {confirmedZoneTouch && (
                <circle
                  data-chart-role="resistance-touch"
                  data-date={item.date}
                  data-price={touchPrice}
                  cx={x(index)}
                  cy={y(touchPrice)}
                  r="3"
                  fill="#f59e0b"
                  stroke="white"
                  strokeWidth="1"
                />
              )}
              <rect
                x={x(index) - Math.max(1, bodyWidth / 2)}
                y={VOLUME_BOTTOM - (item.volume / maximumVolume) * (VOLUME_BOTTOM - VOLUME_TOP)}
                width={Math.max(2, bodyWidth)}
                height={(item.volume / maximumVolume) * (VOLUME_BOTTOM - VOLUME_TOP)}
                fill={color}
                fillOpacity="0.35"
              />
            </g>
          );
        })}
        <line x1={LEFT} x2={WIDTH - RIGHT} y1={VOLUME_BOTTOM} y2={VOLUME_BOTTOM} stroke="#cbd5e1" />
        <text x={LEFT - 8} y={VOLUME_TOP + 9} textAnchor="end" fontSize="10" fontWeight="600" fill="#475569">Volume</text>
        {xTickIndexes.map((index) => (
          <text
            key={index}
            data-chart-role="x-axis-label"
            x={x(index)}
            y={422}
            textAnchor="middle"
            fontSize="11"
            fontWeight="600"
            fill="#475569"
          >
            {shortDate(parsed[index].date, data.timeframe)}
          </text>
        ))}
      </svg>
    </div>
  );
}

export function SetupChartModal({
  stock,
  onClose,
}: {
  stock: StockListItem | null;
  onClose: () => void;
}) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState<"DAILY" | "WEEKLY">("DAILY");
  const chartQuery = useStockChart(stock?.instrumentId ?? null);

  useEffect(() => {
    if (!stock) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = originalOverflow;
      previousFocus?.focus();
    };
  }, [onClose, stock]);

  useEffect(() => {
    setSelectedTimeframe("DAILY");
  }, [stock?.instrumentId]);

  if (!stock) return null;
  const headerChart = chartQuery.data?.charts.find(
    (chart) => chart.timeframe === "DAILY",
  ) ?? chartQuery.data?.charts[0] ?? null;
  const priceSummary = latestPriceSummary(headerChart);
  const selectedChart = chartQuery.data?.charts.find(
    (chart) => chart.timeframe === selectedTimeframe,
  ) ?? chartQuery.data?.charts[0] ?? null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end bg-slate-950/55 p-0 backdrop-blur-[2px] sm:items-center sm:justify-center sm:p-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex max-h-[94vh] w-full flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl sm:max-w-7xl sm:rounded-3xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4 sm:px-6">
          <div className="flex min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h2 id={titleId} className="text-lg font-bold text-slate-950">{stock.companyName}</h2>
              <p className="mt-1 text-sm text-slate-500">{stock.tradingSymbol} · setup candles</p>
            </div>
            {priceSummary && (
              <div className="shrink-0 sm:text-right" aria-label={`${priceSummary.periodLabel} price summary`}>
                <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">Latest close</p>
                <div className="mt-0.5 flex items-baseline gap-2 sm:justify-end">
                  <span className="text-base font-bold text-slate-950">₹{priceLabel(priceSummary.latestClose)}</span>
                  <span className={`text-sm font-bold ${priceSummary.changePercent >= 0 ? "text-emerald-700" : "text-red-700"}`}>
                    {priceSummary.periodLabel}: {signedPercentage(priceSummary.changePercent)}
                  </span>
                </div>
              </div>
            )}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full text-xl text-slate-500 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-blue-600"
            aria-label="Close setup chart"
          >
            ×
          </button>
        </header>
        <div data-testid="chart-modal-content" className="overflow-y-auto p-4 md:overflow-hidden md:p-5">
          {chartQuery.isPending ? (
            <div className="flex min-h-72 items-center justify-center text-sm font-medium text-slate-500" role="status">Loading setup chart…</div>
          ) : chartQuery.isError || !chartQuery.data ? (
            <div className="min-h-72 rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-800" role="alert">
              The stored chart evidence could not be loaded. Close this popup and try again.
            </div>
          ) : (
            <div className="min-w-0 rounded-3xl border border-slate-200 bg-white p-3 shadow-sm md:p-4">
              {chartQuery.data.charts.length > 1 && (
                <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Chart timeframe">
                  {chartQuery.data.charts.map((chart) => {
                    const selected = chart.timeframe === selectedChart?.timeframe;
                    return (
                      <button
                        key={chart.timeframe}
                        type="button"
                        aria-label={`${chart.timeframe === "WEEKLY" ? "Weekly" : "Daily"} — ${chart.technicalStatus.replaceAll("_", " ").toLowerCase()}`}
                        aria-pressed={selected}
                        onClick={() => setSelectedTimeframe(chart.timeframe)}
                        className={`flex min-w-0 items-center gap-2 rounded-xl border px-3 py-2 text-left transition ${
                          selected
                            ? "border-blue-300 bg-blue-50 text-blue-950"
                            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                        }`}
                      >
                        <span className="text-xs font-bold uppercase tracking-wide">
                          {chart.timeframe === "WEEKLY" ? "Weekly" : "Daily"}
                        </span>
                        <TechnicalStatusBadge status={chart.technicalStatus} />
                      </button>
                    );
                  })}
                </div>
              )}
              {selectedChart && (
                <article className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_11rem] md:items-start">
                  <div className="min-w-0 md:order-1">
                    <SetupCandlestickChart data={selectedChart} companyName={chartQuery.data.companyName} />
                  </div>
                  <aside
                    data-chart-role="setup-summary"
                    className="grid grid-cols-2 gap-2 rounded-2xl bg-slate-50 p-3 text-xs font-medium text-slate-600 sm:grid-cols-4 md:order-2 md:grid-cols-1"
                  >
                    <div className="col-span-2 sm:col-span-1">
                      <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                        {selectedChart.timeframe === "WEEKLY" ? "Weekly timeframe" : "Daily timeframe"}
                      </p>
                      <h3 className="mt-1 text-sm font-bold text-slate-950">
                        {selectedChart.timeframe === "WEEKLY" ? "Long-base setup" : "Recent-base setup"}
                      </h3>
                      {chartQuery.data.charts.length === 1 && (
                        <div className="mt-2"><TechnicalStatusBadge status={selectedChart.technicalStatus} /></div>
                      )}
                    </div>
                    <span>Threshold<br /><strong className="text-slate-900">₹{priceLabel(Number(selectedChart.resistanceZoneUpper))}</strong></span>
                    <span>Zone<br /><strong className="text-slate-900">₹{priceLabel(Number(selectedChart.resistanceZoneLower))}–₹{priceLabel(Number(selectedChart.resistanceZoneUpper))}</strong></span>
                    <span>Length<br /><strong className="text-slate-900">{selectedChart.periodCount} {selectedChart.timeframe === "WEEKLY" ? "weeks" : "sessions"}</strong></span>
                  </aside>
                </article>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
