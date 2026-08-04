import { Link, Route, Routes } from "react-router";

import { AppLayout } from "./features/auth/components/AppLayout";
import { LoginPage } from "./features/auth/components/LoginPage";
import { RequireAuth } from "./features/auth/components/RequireAuth";
import { SignupPage } from "./features/auth/components/SignupPage";
import { StockDetail } from "./features/stocks/components/StockDetail";
import { StockList } from "./features/stocks/components/StockList";
import { AdminDashboard } from "./features/admin/components/AdminDashboard";


export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route index element={<StockList />} />
          <Route path="admin/analytics" element={<AdminDashboard />} />
          <Route path="stocks/:instrumentId" element={<StockDetail />} />
          <Route
            path="*"
            element={(
              <div role="alert" className="mt-8 rounded-xl bg-slate-100 p-6">
                Page not found. <Link className="text-blue-700 underline" to="/">Return to the watchlist</Link>.
              </div>
            )}
          />
        </Route>
      </Route>
    </Routes>
  );
}
