import {
  useDeferredValue,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";

import { useSession } from "../../auth/hooks/useAuth";
import { WatchlistApiError } from "../../watchlist/api/watchlist";
import { AddCompaniesModal } from "../../watchlist/components/AddCompaniesModal";
import {
  useFetchFundamentalData,
  useFetchTechnicalData,
  useRerunBreakoutAlgorithm,
  useRemoveInstrument,
  useWatchlist,
} from "../../watchlist/hooks/useWatchlist";
import { useStocks } from "../hooks/useStocks";
import type { StockListItem, StockPageSize, StockSort } from "../types";
import { StockTable } from "./StockTable";


function actionErrorMessage(error: unknown): string {
  if (!(error instanceof WatchlistApiError)) {
    return "Your watchlist could not be updated. Please try again.";
  }
  if (error.code === "WATCHLIST_ITEM_NOT_FOUND") {
    return "That stock is no longer in your watchlist. Refresh the page.";
  }
  if (error.code === "AUTHENTICATION_REQUIRED" || error.code === "CSRF_VALIDATION_FAILED") {
    return "Your sign-in has expired. Refresh the page and sign in again.";
  }
  return "Your watchlist is temporarily unavailable. Please try again.";
}

function SelectChevron({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      className={`pointer-events-none h-4 w-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
    >
      <path d="m6 8 4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface SelectOption<T extends string | number> {
  value: T;
  label: string;
}

function StyledSelect<T extends string | number>({
  label,
  value,
  options,
  onChange,
  className,
}: {
  label: string;
  value: T;
  options: readonly SelectOption<T>[];
  onChange: (value: T) => void;
  className: string;
}) {
  const [open, setOpen] = useState(false);
  const listboxId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const selected = options.find((option) => option.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    function closeOnOutsideClick(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    }
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <span className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
        {label}
      </span>
      <button
        ref={buttonRef}
        type="button"
        role="combobox"
        aria-label={label}
        aria-expanded={open}
        aria-controls={listboxId}
        aria-haspopup="listbox"
        onClick={() => setOpen((current) => !current)}
        className="mt-2 flex h-11 w-full items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-3.5 text-left text-sm font-medium text-slate-800 shadow-sm outline-none transition hover:border-slate-300 hover:bg-slate-50/60 focus-visible:border-blue-500 focus-visible:ring-4 focus-visible:ring-blue-100"
      >
        <span className="truncate">{selected.label}</span>
        <SelectChevron open={open} />
      </button>
      {open && (
        <div
          id={listboxId}
          role="listbox"
          aria-label={`${label} options`}
          className="absolute right-0 z-40 mt-2 w-full min-w-max overflow-hidden rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl shadow-slate-200/70"
        >
          {options.map((option) => {
            const isSelected = option.value === value;
            return (
              <button
                key={String(option.value)}
                type="button"
                role="option"
                aria-selected={isSelected}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                  buttonRef.current?.focus();
                }}
                className={`flex w-full items-center justify-between gap-5 rounded-lg px-3 py-2 text-left text-sm transition focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-blue-600 ${
                  isSelected
                    ? "bg-blue-50 font-semibold text-blue-800"
                    : "font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-950"
                }`}
              >
                <span>{option.label}</span>
                {isSelected && (
                  <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4 shrink-0 text-blue-600">
                    <path d="m5 10 3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

const SORT_OPTIONS: readonly SelectOption<StockSort>[] = [
  { value: "status", label: "Technical status" },
  { value: "market_cap_desc", label: "Market cap: high to low" },
  { value: "market_cap_asc", label: "Market cap: low to high" },
  { value: "day_change_desc", label: "1-day change: high to low" },
  { value: "day_change_asc", label: "1-day change: low to high" },
  { value: "watchlist_change_desc", label: "Since added: high to low" },
  { value: "watchlist_change_asc", label: "Since added: low to high" },
];

const PAGE_SIZE_OPTIONS: readonly SelectOption<StockPageSize>[] = [
  { value: 10, label: "10" },
  { value: 25, label: "25" },
  { value: 50, label: "50" },
  { value: 100, label: "100" },
  { value: "all", label: "All" },
];

export function StockList() {
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [announcement, setAnnouncement] = useState<string | null>(null);
  const [tableSearch, setTableSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<StockSort>("status");
  const [pageSize, setPageSize] = useState<StockPageSize>(50);
  const session = useSession().data;
  const isAdmin = session?.role === "ADMIN";
  const deferredSearch = useDeferredValue(tableSearch.trim());
  const watchlistQuery = useWatchlist();
  const stocksQuery = useStocks({
    page,
    search: deferredSearch,
    sort,
    pageSize,
  });
  const removeMutation = useRemoveInstrument();
  const technicalMutation = useFetchTechnicalData();
  const fundamentalMutation = useFetchFundamentalData();
  const rerunMutation = useRerunBreakoutAlgorithm();
  const adminActionPending = (
    technicalMutation.isPending
    || fundamentalMutation.isPending
    || rerunMutation.isPending
  );
  const totalPages = stocksQuery.data?.totalPages ?? 0;

  useEffect(() => {
    if (totalPages > 0 && page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  if (watchlistQuery.isPending || stocksQuery.isPending) {
    return (
      <section className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" aria-busy="true">
        <div className="px-6 py-5">
          <p className="text-xs font-semibold tracking-[0.16em] text-blue-600 uppercase">Watchlist</p>
        </div>
        <div className="flex items-center gap-3 border-t border-slate-100 px-6 py-10" role="status">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-blue-600" aria-hidden="true" />
          <p className="text-sm text-slate-600">Loading your latest market research…</p>
        </div>
      </section>
    );
  }

  if (watchlistQuery.isError || stocksQuery.isError) {
    return (
      <section className="mt-8 rounded-2xl border border-red-200 bg-red-50 px-6 py-8" role="alert">
        <h1 className="font-semibold text-red-950">Your watchlist is temporarily unavailable</h1>
        <p className="mt-2 text-sm text-red-700">The latest market results could not be loaded. Please try again.</p>
        <button
          type="button"
          className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white"
          onClick={() => {
            void watchlistQuery.refetch();
            void stocksQuery.refetch();
          }}
        >
          Try again
        </button>
      </section>
    );
  }

  const watchlist = watchlistQuery.data;
  const watchlistItemsByInstrument = new Map(
    watchlist.items.map((item) => [item.instrumentId, item]),
  );
  const existingSymbols = new Set(watchlist.items.map((item) => item.tradingSymbol));
  const removingInstrumentId = removeMutation.isPending
    ? removeMutation.variables
    : null;
  const stocks = stocksQuery.data.items;
  const firstVisible = stocksQuery.data.count === 0
    ? 0
    : (stocksQuery.data.page - 1) * stocksQuery.data.pageSize + 1;
  const lastVisible = Math.min(
    stocksQuery.data.page * stocksQuery.data.pageSize,
    stocksQuery.data.count,
  );

  function removeStock(stock: Pick<StockListItem, "instrumentId" | "tradingSymbol">) {
    if (
      isAdmin
      && !window.confirm(
        `Permanently delete ${stock.tradingSymbol} for every user, including all stored market data and analysis?`,
      )
    ) {
      return;
    }
    setAnnouncement(null);
    removeMutation.reset();
    removeMutation.mutate(stock.instrumentId, {
      onSuccess: () => {
        setAnnouncement(
          isAdmin
            ? `${stock.tradingSymbol} and all of its stored data were deleted for every user.`
            : `${stock.tradingSymbol} was removed from your watchlist.`,
        );
      },
    });
  }

  return (
    <>
      <section className="mt-8 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" aria-labelledby="stock-list-heading">
        <header className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className="text-xs font-semibold tracking-[0.16em] text-blue-600 uppercase">
              {isAdmin ? "Research universe" : "Watchlist"}
            </p>
            <h1 id="stock-list-heading" className="mt-1 text-xl font-semibold text-slate-950">
              {isAdmin ? "Tracked companies" : "Your stocks"}
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {isAdmin
                ? `${stocksQuery.data.count} tracked ${stocksQuery.data.count === 1 ? "company" : "companies"}`
                : `${watchlist.count} ${watchlist.count === 1 ? "stock" : "stocks"}${watchlist.watchlistLimit !== null ? ` of ${watchlist.watchlistLimit}` : ""}`}
            </p>
          </div>

          <div className="grid w-full grid-cols-1 gap-2 min-[420px]:w-auto min-[420px]:grid-cols-2 sm:flex sm:flex-wrap">
            {session?.role === "ADMIN" && (
              <>
                <button
                  type="button"
                  disabled={adminActionPending || watchlist.count === 0}
                  onClick={() => {
                    setAnnouncement(null);
                    technicalMutation.reset();
                    technicalMutation.mutate(undefined, {
                      onSuccess: (result) => setAnnouncement(
                        result.scheduledCount > 0
                          ? `Technical data fetch queued for ${result.scheduledCount} ${result.scheduledCount === 1 ? "stock" : "stocks"}.`
                          : result.terminalDataFailureCount > 0
                            ? `No duplicate jobs were queued; ${result.terminalDataFailureCount} ${result.terminalDataFailureCount === 1 ? "stock has a" : "stocks have"} terminal data-quality result for ${result.targetSession}.`
                          : `Technical data is current through ${result.targetSession}.`,
                      ),
                    });
                  }}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-blue-200 px-3 text-sm font-semibold text-blue-700 transition hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50"
                >
                  <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`h-4 w-4 ${technicalMutation.isPending ? "animate-spin" : ""}`}>
                    <path d="M20 11a8.1 8.1 0 0 0-15.5-2M4 4v5h5" />
                    <path d="M4 13a8.1 8.1 0 0 0 15.5 2M20 20v-5h-5" />
                  </svg>
                  Fetch technical data
                </button>
                <button
                  type="button"
                  disabled={adminActionPending || watchlist.count === 0}
                  onClick={() => {
                    setAnnouncement(null);
                    rerunMutation.reset();
                    rerunMutation.mutate(undefined, {
                      onSuccess: (result) => setAnnouncement(
                        result.scheduledCount > 0
                          ? `Algorithm re-run queued for ${result.scheduledCount} ${result.scheduledCount === 1 ? "stock" : "stocks"}.`
                          : result.terminalDataFailureCount > 0
                            ? `No duplicate algorithm jobs were queued; ${result.terminalDataFailureCount} ${result.terminalDataFailureCount === 1 ? "stock has a" : "stocks have"} terminal data-quality result for ${result.targetSession}.`
                          : `No algorithm jobs were queued for ${result.targetSession}.`,
                      ),
                    });
                  }}
                  className="h-11 rounded-xl border border-violet-200 px-3 text-sm font-semibold text-violet-700 transition hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:opacity-50"
                >
                  {rerunMutation.isPending ? "Queueing…" : "Re-run algorithm"}
                </button>
                <button
                  type="button"
                  disabled={adminActionPending || watchlist.count === 0}
                  onClick={() => {
                    setAnnouncement(null);
                    fundamentalMutation.reset();
                    fundamentalMutation.mutate(undefined, {
                      onSuccess: (result) => setAnnouncement(
                        result.scheduledCount > 0
                          ? `Fundamental data fetch queued for ${result.scheduledCount} ${result.scheduledCount === 1 ? "stock" : "stocks"}.`
                          : "No fundamental data jobs were queued.",
                      ),
                    });
                  }}
                  className="h-11 rounded-xl border border-emerald-200 px-3 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 disabled:opacity-50"
                >
                  {fundamentalMutation.isPending ? "Queueing…" : "Fetch fundamental data"}
                </button>
              </>
            )}
            <button
              type="button"
              disabled={watchlist.remainingSlots === 0}
              onClick={() => setAddModalOpen(true)}
              className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              + Add companies
            </button>
          </div>
        </header>

        {announcement && (
          <p className="border-t border-emerald-100 bg-emerald-50 px-5 py-3 text-sm text-emerald-800 sm:px-6" role="status">
            {announcement}
          </p>
        )}
        {(removeMutation.isError || technicalMutation.isError || fundamentalMutation.isError || rerunMutation.isError) && (
          <p className="border-t border-red-100 bg-red-50 px-5 py-3 text-sm text-red-700 sm:px-6" role="alert">
            {actionErrorMessage(removeMutation.error ?? technicalMutation.error ?? fundamentalMutation.error ?? rerunMutation.error)}
          </p>
        )}

        {(stocksQuery.data.count > 0 || tableSearch) && (
          <div className="border-t border-slate-100 bg-slate-50/60 px-5 py-4 sm:px-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <label className="block w-full sm:max-w-md">
                <span className="text-xs font-semibold tracking-wide text-slate-600 uppercase">
                  Search your stocks
                </span>
                <span className="relative mt-2 block">
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-slate-400"
                  >
                    <circle cx="11" cy="11" r="7" />
                    <path d="m20 20-3.5-3.5" />
                  </svg>
                  <input
                    type="search"
                    value={tableSearch}
                    onChange={(event) => {
                      setTableSearch(event.target.value);
                      setPage(1);
                    }}
                    placeholder="Company name or symbol"
                    autoComplete="off"
                    className="block h-11 w-full rounded-xl border border-slate-300 bg-white pr-20 pl-10 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                  />
                  {tableSearch && (
                    <button
                      type="button"
                      onClick={() => {
                        setTableSearch("");
                        setPage(1);
                      }}
                      className="absolute top-1/2 right-2 -translate-y-1/2 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-blue-600"
                    >
                      Clear
                    </button>
                  )}
                </span>
              </label>
              <div className="flex w-full flex-col gap-3 min-[430px]:flex-row sm:w-auto sm:justify-end">
                <StyledSelect
                  label="Sort by"
                  value={sort}
                  options={SORT_OPTIONS}
                  onChange={(nextSort) => {
                    setSort(nextSort);
                    setPage(1);
                  }}
                  className="min-w-0 flex-1 sm:w-64 sm:flex-none"
                />
                <StyledSelect
                  label="Rows"
                  value={pageSize}
                  options={PAGE_SIZE_OPTIONS}
                  onChange={(nextPageSize) => {
                    setPageSize(nextPageSize);
                    setPage(1);
                  }}
                  className="min-w-0 flex-1 sm:w-28 sm:flex-none"
                />
              </div>
            </div>
            <p className="mt-3 text-sm text-slate-500" aria-live="polite">
              {deferredSearch
                ? `${stocksQuery.data.count} matching ${stocksQuery.data.count === 1 ? "stock" : "stocks"}`
                : `Showing ${firstVisible}-${lastVisible} of ${stocksQuery.data.count} ${stocksQuery.data.count === 1 ? "stock" : "stocks"}`}
              {stocksQuery.isFetching ? " — Updating…" : ""}
            </p>
          </div>
        )}

        {!isAdmin && watchlist.count === 0 ? (
          <div className="border-t border-slate-100 px-6 py-12 text-center">
            <h2 className="font-semibold text-slate-900">Start your watchlist</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
              Add NSE companies to follow their latest end-of-day breakout research.
            </p>
            <button
              type="button"
              onClick={() => setAddModalOpen(true)}
              className="mt-5 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
            >
              Add companies
            </button>
          </div>
        ) : stocks.length > 0 ? (
          <StockTable
            items={stocks}
            watchlistItemsByInstrument={watchlistItemsByInstrument}
            removingInstrumentId={removingInstrumentId}
            onRemove={removeStock}
            globalDelete={isAdmin}
          />
        ) : deferredSearch ? (
          <div className="border-t border-slate-100 px-6 py-12 text-center">
            <h2 className="font-semibold text-slate-900">No matching stocks</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
              Try another company name or trading symbol.
            </p>
            <button
              type="button"
              onClick={() => {
                setTableSearch("");
                setPage(1);
              }}
              className="mt-5 rounded-xl border border-blue-200 px-4 py-2.5 text-sm font-semibold text-blue-700 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              Clear search
            </button>
          </div>
        ) : isAdmin ? (
          <div className="border-t border-slate-100 px-6 py-12 text-center">
            <h2 className="font-semibold text-slate-900">Analysis is still preparing</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
              Tracked companies will appear here as the worker completes their latest research.
            </p>
          </div>
        ) : null}

        {stocksQuery.data.totalPages > 1 && (
          <nav
            className="flex items-center justify-between gap-4 border-t border-slate-100 px-5 py-4 sm:px-6"
            aria-label="Stock table pagination"
          >
            <button
              type="button"
              disabled={page <= 1 || stocksQuery.isFetching}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <p className="text-sm text-slate-600" aria-live="polite">
              Page {stocksQuery.data.page} of {stocksQuery.data.totalPages}
            </p>
            <button
              type="button"
              disabled={page >= stocksQuery.data.totalPages || stocksQuery.isFetching}
              onClick={() => setPage((current) => current + 1)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </nav>
        )}
      </section>

      <AddCompaniesModal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onAdded={(count) => {
          setAnnouncement(`${count} ${count === 1 ? "company was" : "companies were"} added to your watchlist.`);
        }}
        existingSymbols={existingSymbols}
        remainingSlots={watchlist.remainingSlots}
      />
    </>
  );
}
