import { Navigate } from "react-router";

import { useSession } from "../../auth/hooks/useAuth";
import { useAdminAnalytics } from "../hooks/useAdminAnalytics";


function MetricCard({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{label}</p>
      <p className="mt-2 text-3xl font-bold text-slate-950">{value}</p>
      {note && <p className="mt-1 text-xs text-slate-500">{note}</p>}
    </article>
  );
}


export function AdminDashboard() {
  const session = useSession().data;
  const analytics = useAdminAnalytics();
  if (session?.role !== "ADMIN") return <Navigate to="/" replace />;
  if (analytics.isPending) return <p className="mt-8 text-slate-600" role="status">Loading admin analytics...</p>;
  if (analytics.isError || !analytics.data) return <p className="mt-8 rounded-xl bg-red-50 p-4 text-red-800" role="alert">Admin analytics are temporarily unavailable.</p>;

  const data = analytics.data;
  const statuses = Object.entries(data.stocks.setupDistribution)
    .filter(([, count]) => count > 0)
    .sort((left, right) => right[1] - left[1]);
  return (
    <section className="py-8">
      <div>
        <p className="text-sm font-semibold text-blue-700">Administration</p>
        <h1 className="mt-1 text-3xl font-bold text-slate-950">Application analytics</h1>
        <p className="mt-2 text-sm text-slate-500">Current shared database state. Refreshes every minute.</p>
      </div>

      <h2 className="mt-8 text-lg font-bold text-slate-900">Users</h2>
      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="Registered users" value={data.users.registeredUsers} />
        <MetricCard label="Active last 7 days" value={data.users.activeUsers7d} note={`${data.users.newUsers7d} new registrations`} />
        <MetricCard label="Active last 30 days" value={data.users.activeUsers30d} note={`${data.users.newUsers30d} new registrations`} />
        <MetricCard label="Telegram connected" value={data.users.telegramConnectedUsers} />
      </div>

      <h2 className="mt-8 text-lg font-bold text-slate-900">Stocks and memberships</h2>
      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="Tracked stocks" value={data.stocks.trackedStocks} />
        <MetricCard label="Active memberships" value={data.stocks.activeWatchlistMemberships} />
        <MetricCard label="Average stocks per user" value={data.stocks.averageStocksPerRegisteredUser.toFixed(2)} />
      </div>

      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-bold text-slate-950">Current setup distribution</h2>
        {statuses.length ? <ul className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{statuses.map(([status, count]) => <li key={status} className="flex justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm"><span>{status.replaceAll("_", " ")}</span><strong>{count}</strong></li>)}</ul> : <p className="mt-2 text-sm text-slate-500">No current analyses.</p>}
      </div>

      <h2 className="mt-8 text-lg font-bold text-slate-900">Worker queue</h2>
      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="Ready pending jobs" value={data.jobs.pendingJobs} />
        <MetricCard label="Retry scheduled" value={data.jobs.retryScheduledJobs} />
        <MetricCard label="Running jobs" value={data.jobs.runningJobs} />
      </div>
      <p className="mt-4 text-xs text-slate-500">Latest analysis session: {data.jobs.latestAnalysisDate ?? "None"}. API latency, throughput and error percentiles are exposed through the protected Prometheus endpoint.</p>
    </section>
  );
}
