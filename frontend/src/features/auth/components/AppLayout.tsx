import { Link, Navigate, Outlet } from "react-router";

import { useSession } from "../hooks/useAuth";
import { ProfileMenu } from "./ProfileMenu";


export function AppLayout() {
  const sessionQuery = useSession();
  const session = sessionQuery.data;

  if (!session) return <Navigate to="/login" replace />;

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
      <header className="flex items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div className="min-w-0">
          <Link to="/" className="text-lg font-semibold tracking-[0.14em] text-blue-700 uppercase sm:text-xl">
            Breakout tracker
          </Link>
          <p className="mt-1 hidden text-sm text-slate-500 sm:block">
            End-of-day breakout research for your watchlist
          </p>
        </div>
        <div className="flex items-center gap-3">
          {session.role === "ADMIN" && (
            <Link className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 hover:text-blue-700" to="/admin/analytics">Analytics</Link>
          )}
          <ProfileMenu session={session} />
        </div>
      </header>
      <Outlet />
    </main>
  );
}
