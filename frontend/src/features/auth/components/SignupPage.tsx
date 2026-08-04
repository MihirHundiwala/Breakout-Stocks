import { type FormEvent, useId, useState } from "react";
import { Link, Navigate } from "react-router";

import { AuthError } from "../api/auth";
import { useSession, useSignup } from "../hooks/useAuth";


const minimumPasswordLength = 12;

function signupErrorMessage(error: unknown): string {
  if (!(error instanceof AuthError)) {
    return "Your account could not be created. Please try again.";
  }
  if (error.code === "USERNAME_UNAVAILABLE") {
    return "That username is unavailable. Try a different one.";
  }
  if (error.code === "PASSWORD_TOO_SHORT") {
    return `Use at least ${minimumPasswordLength} characters for your password.`;
  }
  return "Sign up is temporarily unavailable. Please try again.";
}

export function SignupPage() {
  const usernameId = useId();
  const passwordId = useId();
  const confirmationId = useId();
  const errorId = useId();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const sessionQuery = useSession();
  const signupMutation = useSignup();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    signupMutation.reset();
    if (password !== confirmation) {
      setFormError("The passwords do not match.");
      return;
    }
    setFormError(null);
    try {
      await signupMutation.mutateAsync({ username: username.trim(), password });
      setPassword("");
      setConfirmation("");
    } catch {
      // TanStack Query retains the typed error for the alert below.
    }
  }

  if (sessionQuery.data) {
    return <Navigate to="/" replace />;
  }

  const displayedError = formError
    ?? (signupMutation.isError ? signupErrorMessage(signupMutation.error) : null);

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8 sm:px-6 sm:py-10">
      <section className="w-full max-w-md overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60">
        <div className="bg-gradient-to-br from-blue-700 to-indigo-600 px-6 py-7 text-white sm:px-8 sm:py-8">
          <p className="text-xs font-semibold tracking-[0.18em] text-blue-100 uppercase">
            Breakout tracker
          </p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">
            Create your watchlist
          </h1>
          <p className="mt-2 text-sm leading-6 text-blue-100">
            Open a personal account for end-of-day stock research.
          </p>
        </div>

        <form className="space-y-4 px-6 py-6 sm:px-8" onSubmit={submit}>
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
              minLength={3}
              maxLength={64}
              pattern="[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
              title="Use letters, numbers, dots, underscores, or hyphens; start and end with a letter or number."
              disabled={signupMutation.isPending}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="mt-2 block w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-slate-950 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-100"
            />
            <p className="mt-1.5 text-xs leading-5 text-slate-500">
              3–64 characters: letters, numbers, dots, underscores, or hyphens.
            </p>
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700" htmlFor={passwordId}>
              Password
            </label>
            <input
              id={passwordId}
              name="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={minimumPasswordLength}
              maxLength={1024}
              disabled={signupMutation.isPending}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 block w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-slate-950 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-100"
            />
            <p className="mt-1.5 text-xs text-slate-500">Use at least 12 characters.</p>
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700" htmlFor={confirmationId}>
              Confirm password
            </label>
            <input
              id={confirmationId}
              name="password-confirmation"
              type="password"
              autoComplete="new-password"
              required
              minLength={minimumPasswordLength}
              maxLength={1024}
              disabled={signupMutation.isPending}
              value={confirmation}
              aria-describedby={displayedError ? errorId : undefined}
              onChange={(event) => setConfirmation(event.target.value)}
              className="mt-2 block w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-slate-950 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100 disabled:bg-slate-100"
            />
          </div>

          {displayedError && (
            <p id={errorId} className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
              {displayedError}
            </p>
          )}

          <button
            type="submit"
            disabled={signupMutation.isPending || !username.trim() || !password || !confirmation}
            className="w-full rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-55"
          >
            {signupMutation.isPending ? "Creating account…" : "Create account"}
          </button>

          <p className="text-center text-sm text-slate-600">
            Already have an account?{" "}
            <Link className="font-semibold text-blue-700 hover:text-blue-800" to="/login">
              Sign in
            </Link>
          </p>
        </form>
      </section>
    </main>
  );
}
