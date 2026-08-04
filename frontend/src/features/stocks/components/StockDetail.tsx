import { Link, useParams } from "react-router";

import { useStockDetail } from "../hooks/useStockDetail";
import type { JsonValue } from "../types";
import {
  formatAnalysisDate,
  formatPrice,
  formatSignedPercentage,
} from "../formatters";
import {
  FundamentalCoverageBadge,
  StockAnalysisStatusBadge,
} from "./StatusBadge";


function objectValue(value: JsonValue | undefined): Record<string, JsonValue> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value
    : null;
}

function displayMetric(value: JsonValue | undefined, suffix = ""): string {
  if (typeof value !== "string" && typeof value !== "number") {
    return "Unknown";
  }
  return `${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}${suffix}`;
}

function RatioTable({ ratios }: { ratios: Record<string, JsonValue> | null }) {
  if (ratios === null || Object.keys(ratios).length === 0) {
    return <p className="mt-4 text-sm text-slate-500">Ratio data is unknown.</p>;
  }
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr><th className="py-2 pr-4">Ratio</th><th className="py-2 pr-4">Company</th><th className="py-2">Sector</th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {Object.entries(ratios).map(([name, raw]) => {
            const ratio = objectValue(raw);
            return (
              <tr key={name}>
                <th scope="row" className="py-3 pr-4 font-medium text-slate-900">{name}</th>
                <td className="py-3 pr-4 tabular-nums">{displayMetric(ratio?.company_value)}</td>
                <td className="py-3 tabular-nums">{displayMetric(ratio?.sector_value)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function StockDetail() {
  const rawId = useParams().instrumentId;
  const parsedId = rawId === undefined ? null : Number(rawId);
  const instrumentId = parsedId !== null && Number.isSafeInteger(parsedId) && parsedId > 0
    ? parsedId
    : null;
  const detailQuery = useStockDetail(instrumentId);

  if (instrumentId === null) {
    return <div role="alert" className="mt-8 rounded-xl bg-red-50 p-6 text-red-800">Invalid stock link.</div>;
  }
  if (detailQuery.isPending) {
    return <div role="status" className="mt-8 rounded-xl border border-slate-200 bg-white p-8">Loading stock research…</div>;
  }
  if (detailQuery.isError) {
    return (
      <div role="alert" className="mt-8 rounded-xl border border-red-200 bg-red-50 p-6">
        <p className="font-semibold text-red-900">Stock research is unavailable.</p>
        <button className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white" onClick={() => void detailQuery.refetch()}>Try again</button>
      </div>
    );
  }

  const { stock, fundamentals, periods } = detailQuery.data;
  const profile = objectValue(fundamentals?.metrics.profile);
  const ratios = objectValue(fundamentals?.metrics.ratios);

  return (
    <div className="mt-8">
      <Link to="/" className="text-sm font-semibold text-blue-700 hover:underline">← Back to watchlist</Link>
      <section className="mt-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">{stock.exchange}:{stock.tradingSymbol}</p>
            <h1 className="mt-2 text-2xl font-bold text-slate-950">{stock.companyName}</h1>
            <p className="mt-2 text-sm text-slate-500">Market data through {formatAnalysisDate(stock.analysisDate)}</p>
          </div>
          <StockAnalysisStatusBadge
            status={stock.technicalStatus}
            operationalState={stock.operationalState}
            errorCode={stock.analysisErrorCode}
          />
        </div>
        <dl className="mt-6 grid gap-4 sm:grid-cols-2">
          <div><dt className="text-xs text-slate-500">Close</dt><dd className="mt-1 text-lg font-semibold">{formatPrice(stock.closePrice)}</dd></div>
          <div><dt className="text-xs text-slate-500">1-day change</dt><dd className="mt-1 text-lg font-semibold">{formatSignedPercentage(stock.dayChangePercent)}</dd></div>
        </dl>
      </section>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-950">Fundamental research</h2>
          <FundamentalCoverageBadge status={fundamentals?.coverage ?? "UNKNOWN"} />
        </div>
        {fundamentals === null ? (
          <p className="mt-4 text-sm text-slate-500">Company financial data is not available yet. The setup status remains available independently.</p>
        ) : (
          <>
            <p className="mt-3 text-sm text-slate-500">{fundamentals.availableGroupCount} of {fundamentals.expectedGroupCount} expected groups available · fetched {formatAnalysisDate(fundamentals.asOfDate)}</p>
            <h3 className="mt-6 font-semibold text-slate-900">{typeof profile?.sector === "string" ? profile.sector : "Sector unknown"}</h3>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">{typeof profile?.description === "string" ? profile.description : "Company description is unknown."}</p>
            <h3 className="mt-7 font-semibold text-slate-900">Company vs sector ratios</h3>
            <RatioTable ratios={ratios} />
          </>
        )}
      </section>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-950">Annual statement history</h2>
        {periods.length === 0 ? <p className="mt-4 text-sm text-slate-500">No statement periods are available.</p> : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500"><tr><th className="py-2 pr-4">Period</th><th className="py-2 pr-4">Revenue (Cr)</th><th className="py-2 pr-4">Net profit (Cr)</th><th className="py-2 pr-4">Operating cash flow (Cr)</th><th className="py-2">Assets (Cr)</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {periods.map((period) => <tr key={`${period.periodEnd}-${period.statementBasis}`}><th scope="row" className="py-3 pr-4 font-medium">{formatAnalysisDate(period.periodEnd)}</th><td className="py-3 pr-4 tabular-nums">{displayMetric(period.metrics["income.revenue"])}</td><td className="py-3 pr-4 tabular-nums">{displayMetric(period.metrics["income.net_profit"])}</td><td className="py-3 pr-4 tabular-nums">{displayMetric(period.metrics["cash_flow.operating"])}</td><td className="py-3 tabular-nums">{displayMetric(period.metrics["balance.total_assets"])}</td></tr>)}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
