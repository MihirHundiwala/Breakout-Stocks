import { Navigate, Outlet, useLocation } from "react-router";

import { useSession } from "../hooks/useAuth";


export function RequireAuth() {
  const sessionQuery = useSession();
  const location = useLocation();

  if (sessionQuery.isPending) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4" role="status">
        <div className="flex items-center gap-3 text-sm text-slate-600">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-blue-600" aria-hidden="true" />
          Opening your watchlist…
        </div>
      </main>
    );
  }

  if (sessionQuery.isError) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <section className="max-w-md rounded-2xl border border-amber-200 bg-amber-50 p-6" role="alert">
          <h1 className="font-semibold text-amber-950">Sign in check unavailable</h1>
          <p className="mt-2 text-sm text-amber-800">Please check your connection and try again.</p>
          <button className="mt-4 text-sm font-semibold text-amber-900 underline" onClick={() => void sessionQuery.refetch()}>
            Try again
          </button>
        </section>
      </main>
    );
  }

  if (!sessionQuery.data) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }

  return <Outlet />;
}
