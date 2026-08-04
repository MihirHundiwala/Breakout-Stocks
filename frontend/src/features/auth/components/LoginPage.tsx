import { type FormEvent, useId, useState } from "react";
import { Link, Navigate, useLocation } from "react-router";

import { AuthError } from "../api/auth";
import { useLogin, useSession } from "../hooks/useAuth";


function loginErrorMessage(error: unknown): string {
  if (!(error instanceof AuthError)) {
    return "Sign in could not be completed. Please try again.";
  }
  if (error.code === "INVALID_CREDENTIALS") {
    return "The username or password is incorrect.";
  }
  if (error.code === "AUTH_NOT_CONFIGURED") {
    return "Sign in has not been configured on the server.";
  }
  return "Sign in is temporarily unavailable. Please try again.";
}

interface LoginLocationState {
  from?: string;
}

export function LoginPage() {
  const usernameId = useId();
  const passwordId = useId();
  const errorId = useId();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const sessionQuery = useSession();
  const loginMutation = useLogin();
  const location = useLocation();
  const destination =
    (location.state as LoginLocationState | null)?.from ?? "/";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    loginMutation.reset();
    try {
      await loginMutation.mutateAsync({ username: username.trim(), password });
      setPassword("");
    } catch {
      // TanStack Query retains the typed error for the alert below.
    }
  }

  if (sessionQuery.data) {
    return <Navigate to={destination} replace />;
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <section className="w-full max-w-md overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60">
        <div className="bg-gradient-to-br from-blue-700 to-indigo-600 px-6 py-8 text-white sm:px-8">
          <p className="text-xs font-semibold tracking-[0.18em] text-blue-100 uppercase">
            Breakout tracker
          </p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">
            Welcome back
          </h1>
          <p className="mt-2 text-sm leading-6 text-blue-100">
            Sign in to view your end-of-day stock research.
          </p>
        </div>

        <form className="space-y-5 px-6 py-7 sm:px-8" onSubmit={submit}>
          <div>
            <label className="text-sm font-medium text-slate-700" htmlFor={usernameId}>
              Username
            </label>
            <input
              id={usernameId}
              name="username"
              type="text"
              autoComplete="username"
              autoFocus
              required
              maxLength={64}
              disabled={loginMutation.isPending}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="mt-2 block w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-slate-950 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-100"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700" htmlFor={passwordId}>
              Password
            </label>
            <input
              id={passwordId}
              name="password"
              type="password"
              autoComplete="current-password"
              required
              maxLength={1024}
              disabled={loginMutation.isPending}
              value={password}
              aria-describedby={loginMutation.isError ? errorId : undefined}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 block w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-slate-950 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-100"
            />
          </div>

          {loginMutation.isError && (
            <p id={errorId} className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
              {loginErrorMessage(loginMutation.error)}
            </p>
          )}

          {sessionQuery.isError && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
              The current session could not be checked. You can still try to sign in.
            </p>
          )}

          <button
            type="submit"
            disabled={loginMutation.isPending || !username.trim() || !password}
            className="w-full rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-55"
          >
            {loginMutation.isPending ? "Signing in…" : "Sign in"}
          </button>

          <p className="text-center text-sm text-slate-600">
            New here?{" "}
            <Link className="font-semibold text-blue-700 hover:text-blue-800" to="/signup">
              Create an account
            </Link>
          </p>
        </form>
      </section>
    </main>
  );
}
