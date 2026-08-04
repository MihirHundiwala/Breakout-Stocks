import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";

import type { Session } from "../types";
import { useLogout } from "../hooks/useAuth";
import { useConnectTelegram, useTelegramConnection } from "../../telegram/hooks/useTelegram";

function ProfileIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8"><path d="M20 21a8 8 0 0 0-16 0" /><circle cx="12" cy="7" r="4" /></svg>;
}

function ChevronIcon({ open }: { open: boolean }) {
  return <svg aria-hidden="true" viewBox="0 0 20 20" className={`h-4 w-4 fill-none stroke-current transition ${open ? "rotate-180" : ""}`} strokeWidth="2"><path d="m6 8 4 4 4-4" /></svg>;
}

function TelegramIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-current"><path d="M21.7 3.3a1.2 1.2 0 0 0-1.2-.2L3.3 9.7c-1.1.4-1.1 1.1-.2 1.4l4.4 1.4 1.7 5.2c.2.7.1 1 .8 1 .5 0 .8-.2 1-.4l2.1-2 4.4 3.2c.8.5 1.4.2 1.6-.8l2.9-13.8c.3-1.2-.5-1.8-1.3-1.6ZM9.2 12.2l8.6-5.4c.4-.2.8-.1.5.2l-7.1 6.4-.3 3.2-1.7-4.4Z" /></svg>;
}

export function ProfileMenu({ session }: { session: Session }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const logoutMutation = useLogout();
  const connectionQuery = useTelegramConnection();
  const connectMutation = useConnectTelegram();
  const connection = connectionQuery.data;

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", closeOutside);
    document.addEventListener("keydown", closeEscape);
    return () => {
      document.removeEventListener("mousedown", closeOutside);
      document.removeEventListener("keydown", closeEscape);
    };
  }, [open]);

  const connect = () => {
    // Create the tab during the click event so browsers do not treat the
    // eventual Telegram navigation as an unsolicited popup.
    const telegramWindow = window.open("", "_blank");
    if (telegramWindow) telegramWindow.opener = null;
    connectMutation.mutate(undefined, {
      onSuccess: (result) => {
        if (result.botUrl && telegramWindow) {
          telegramWindow.location.href = result.botUrl;
        } else if (!result.botUrl) {
          telegramWindow?.close();
        }
      },
      onError: () => telegramWindow?.close(),
    });
  };

  return (
    <div className="relative" ref={containerRef}>
      <button type="button" aria-label="Open profile menu" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((value) => !value)} className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-2.5 py-2 text-left text-slate-700 shadow-sm transition hover:border-blue-200 hover:bg-blue-50/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-blue-700"><ProfileIcon /></span>
        <span className="hidden min-w-0 sm:block"><span className="block max-w-36 truncate text-sm font-bold text-slate-900">{session.username}</span><span className="block text-[11px] font-medium text-slate-500">{session.role === "ADMIN" ? "Administrator" : "Investor"}</span></span>
        <ChevronIcon open={open} />
      </button>

      {open && (
        <div role="menu" className="absolute right-0 z-40 mt-2 w-72 overflow-hidden rounded-2xl border border-slate-200 bg-white p-2 shadow-xl shadow-slate-900/10">
          <div className="flex items-center gap-3 px-3 py-3"><span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-blue-700"><ProfileIcon /></span><div className="min-w-0"><p className="truncate text-sm font-bold text-slate-950">{session.username}</p><p className="text-xs text-slate-500">{session.role === "ADMIN" ? "Administrator" : "Investor"}</p></div></div>
          <div className="my-1 border-t border-slate-100" />
          <div className="flex items-center justify-between gap-3 rounded-xl px-3 py-3">
            <div className="flex min-w-0 items-center gap-3 text-sky-600"><TelegramIcon /><div className="min-w-0"><p className="text-sm font-semibold text-slate-900">Telegram alerts</p>{connection?.connected ? <p className="flex items-center gap-1.5 truncate text-xs font-semibold text-emerald-700"><span className="h-2 w-2 shrink-0 rounded-full bg-emerald-500" />Connected{connection.username ? ` as @${connection.username}` : ""}</p> : connection?.pending ? <p className="text-xs font-medium text-amber-700">Waiting for Telegram Start</p> : <p className="text-xs text-slate-500">Setup-change notifications</p>}</div></div>
            {connection?.available && !connection.connected && <button type="button" disabled={connectMutation.isPending} onClick={connect} className="shrink-0 rounded-lg border border-sky-200 bg-sky-50 px-2.5 py-1.5 text-xs font-bold text-sky-700 transition hover:bg-sky-100 disabled:opacity-50">{connection.pending ? "Open" : connectMutation.isPending ? "Opening…" : "Connect"}</button>}
          </div>
          {connection && !connection.available && <p className="px-3 pb-2 text-xs text-slate-500">Telegram is not configured by the administrator.</p>}
          {connectMutation.isError && <p className="px-3 pb-2 text-xs font-medium text-red-700" role="alert">Telegram could not be opened. Please try again.</p>}
          <div className="my-1 border-t border-slate-100" />
          <button type="button" role="menuitem" disabled={logoutMutation.isPending} onClick={() => logoutMutation.mutate(undefined, { onSuccess: () => navigate("/login", { replace: true }) })} className="w-full rounded-xl px-3 py-2.5 text-left text-sm font-semibold text-slate-700 transition hover:bg-slate-100 hover:text-slate-950 disabled:opacity-50">{logoutMutation.isPending ? "Signing out…" : "Log out"}</button>
        </div>
      )}
    </div>
  );
}
