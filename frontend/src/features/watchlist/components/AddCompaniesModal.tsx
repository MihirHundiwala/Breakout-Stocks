import { useDeferredValue, useEffect, useId, useRef, useState } from "react";

import { WatchlistApiError } from "../api/watchlist";
import { useAddInstruments, useInstrumentSearch } from "../hooks/useWatchlist";
import type { InstrumentCandidate } from "../types";


function addErrorMessage(error: unknown): string {
  if (!(error instanceof WatchlistApiError)) {
    return "The selected companies could not be added. Please try again.";
  }
  if (error.code === "WATCHLIST_LIMIT_EXCEEDED") {
    return `Your watchlist can contain up to ${error.limit ?? "the allowed number of"} stocks. Review your selection and try again.`;
  }
  if (error.code === "UPSTOX_INSTRUMENT_NOT_FOUND") {
    return "One selected company is no longer available. Search again and retry.";
  }
  if (error.code === "MARKET_DATA_RATE_LIMITED") {
    return "Company search is busy right now. Please wait a moment and try again.";
  }
  if (error.code === "CSRF_VALIDATION_FAILED" || error.code === "AUTHENTICATION_REQUIRED") {
    return "Your sign-in has expired. Refresh the page and sign in again.";
  }
  return "Company information is temporarily unavailable. Please try again.";
}

export function AddCompaniesModal({
  open,
  onClose,
  onAdded,
  existingSymbols,
  remainingSlots,
}: {
  open: boolean;
  onClose: () => void;
  onAdded: (count: number) => void;
  existingSymbols: ReadonlySet<string>;
  remainingSlots: number | null;
}) {
  const headingId = useId();
  const descriptionId = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  const [searchText, setSearchText] = useState("");
  const [selected, setSelected] = useState<InstrumentCandidate[]>([]);
  const deferredSearch = useDeferredValue(searchText.trim());
  const searchQuery = useInstrumentSearch(deferredSearch, open);
  const addMutation = useAddInstruments();
  const mutationPendingRef = useRef(false);
  mutationPendingRef.current = addMutation.isPending;

  useEffect(() => {
    if (!open) {
      setSearchText("");
      setSelected([]);
      addMutation.reset();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    searchRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !mutationPendingRef.current) onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = originalOverflow;
      previouslyFocused?.focus();
    };
  }, [onClose, open]);

  if (!open) return null;

  const selectedIsins = new Set(selected.map((item) => item.isin));
  const atSelectionLimit =
    remainingSlots !== null && selected.length >= remainingSlots;

  function toggle(candidate: InstrumentCandidate) {
    if (selectedIsins.has(candidate.isin)) {
      setSelected((items) => items.filter((item) => item.isin !== candidate.isin));
      return;
    }
    if (atSelectionLimit || existingSymbols.has(candidate.tradingSymbol)) return;
    setSelected((items) => [...items, candidate]);
  }

  async function save() {
    if (selected.length === 0) return;
    addMutation.reset();
    try {
      await addMutation.mutateAsync(selected.map((item) => item.isin));
      onAdded(selected.length);
      onClose();
    } catch {
      // The mutation keeps its typed error for the alert below.
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end bg-slate-950/50 p-0 backdrop-blur-[2px] sm:items-center sm:justify-center sm:p-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !addMutation.isPending) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        aria-describedby={descriptionId}
        className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl sm:max-w-2xl sm:rounded-3xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-5 sm:px-6">
          <div>
            <h2 id={headingId} className="text-lg font-semibold text-slate-950">
              Add companies
            </h2>
            <p id={descriptionId} className="mt-1 text-sm text-slate-500">
              Search NSE companies and select one or more to add together.
            </p>
          </div>
          <button
            type="button"
            aria-label="Close add companies"
            disabled={addMutation.isPending}
            onClick={onClose}
            className="rounded-full p-2 text-xl leading-none text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-blue-600 disabled:opacity-50"
          >
            ×
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
          <label className="block text-sm font-medium text-slate-700">
            Search by company, symbol, or ISIN
            <input
              ref={searchRef}
              type="search"
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="e.g. RELIANCE"
              autoComplete="off"
              className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-slate-950 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
            />
          </label>

          {remainingSlots !== null && (
            <p className="mt-2 text-xs text-slate-500">
              {remainingSlots === 0
                ? "Your watchlist is full. Remove a stock before adding another."
                : `${remainingSlots} ${remainingSlots === 1 ? "place" : "places"} available in your watchlist.`}
            </p>
          )}

          {selected.length > 0 && (
            <div className="mt-4" aria-label="Selected companies">
              <p className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Selected ({selected.length})
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {selected.map((item) => (
                  <button
                    type="button"
                    key={item.isin}
                    onClick={() => toggle(item)}
                    className="rounded-full bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-800 hover:bg-blue-100"
                    aria-label={`Remove ${item.companyName} from selection`}
                  >
                    {item.tradingSymbol} ×
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="mt-5">
            {deferredSearch.length < 2 && (
              <p className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
                Enter at least two characters to search.
              </p>
            )}
            {deferredSearch.length >= 2 && searchQuery.isPending && (
              <p className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500" role="status">
                Searching companies…
              </p>
            )}
            {deferredSearch.length >= 2 && searchQuery.isError && (
              <p className="rounded-xl bg-red-50 px-4 py-4 text-sm text-red-700" role="alert">
                Company search is temporarily unavailable. Please try again.
              </p>
            )}
            {searchQuery.isSuccess && searchQuery.data.count === 0 && (
              <p className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
                No matching NSE companies were found.
              </p>
            )}
            {searchQuery.data && searchQuery.data.count > 0 && (
              <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200">
                {searchQuery.data.items.map((item) => {
                  const alreadyAdded = existingSymbols.has(item.tradingSymbol);
                  const checked = selectedIsins.has(item.isin);
                  const disabled = alreadyAdded || (!checked && atSelectionLimit);
                  return (
                    <li key={item.isin}>
                      <label className={`flex items-center gap-3 px-4 py-3 ${disabled ? "cursor-not-allowed bg-slate-50 opacity-60" : "cursor-pointer hover:bg-blue-50/60"}`}>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={disabled}
                          onChange={() => toggle(item)}
                          className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-slate-900">
                            {item.companyName}
                          </span>
                          <span className="mt-0.5 block text-xs text-slate-500">
                            {item.exchange}:{item.tradingSymbol}
                            {alreadyAdded ? " · Already in your watchlist" : ""}
                          </span>
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {addMutation.isError && (
            <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
              {addErrorMessage(addMutation.error)}
            </p>
          )}
        </div>

        <footer className="flex flex-col-reverse gap-3 border-t border-slate-200 bg-slate-50 px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
          <button
            type="button"
            disabled={addMutation.isPending}
            onClick={onClose}
            className="rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-200 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={selected.length === 0 || addMutation.isPending}
            onClick={() => void save()}
            className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {addMutation.isPending
              ? "Adding companies…"
              : `Save${selected.length > 0 ? ` (${selected.length})` : ""}`}
          </button>
        </footer>
      </section>
    </div>
  );
}
