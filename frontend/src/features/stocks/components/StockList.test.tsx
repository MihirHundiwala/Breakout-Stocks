import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";

import { useSession } from "../../auth/hooks/useAuth";
import {
  useAddInstruments,
  useFetchFundamentalData,
  useFetchTechnicalData,
  useInstrumentSearch,
  useRerunBreakoutAlgorithm,
  useRemoveInstrument,
  useWatchlist,
} from "../../watchlist/hooks/useWatchlist";
import { useStocks } from "../hooks/useStocks";
import type { StockListData } from "../types";
import { StockList } from "./StockList";


vi.mock("../../auth/hooks/useAuth", () => ({ useSession: vi.fn() }));
vi.mock("../../watchlist/hooks/useWatchlist", () => ({
  useAddInstruments: vi.fn(),
  useFetchFundamentalData: vi.fn(),
  useFetchTechnicalData: vi.fn(),
  useInstrumentSearch: vi.fn(),
  useRerunBreakoutAlgorithm: vi.fn(),
  useRemoveInstrument: vi.fn(),
  useWatchlist: vi.fn(),
}));
vi.mock("../hooks/useStocks", () => ({ useStocks: vi.fn() }));

const stockRefetch = vi.fn();
const watchlistRefetch = vi.fn();
const removeMutate = vi.fn();
const removeReset = vi.fn();
const addMutateAsync = vi.fn();
const addReset = vi.fn();

const stockData: StockListData = {
  count: 1,
  page: 1,
  pageSize: 50,
  totalPages: 1,
  items: [{
    instrumentId: 1,
    companyName: "Aurora Industries Limited",
    exchange: "NSE",
    tradingSymbol: "AURORA",
    analysisDate: "2026-07-22",
    technicalStatus: "SETUP_FOUND",
    fundamentalCoverage: "COMPLETE",
    closePrice: "512.80",
    dayChangePercent: "1.29",
    marketCapCrore: null,
    source: "FIXTURE",
    sourceFetchedAt: "2026-07-22T18:00:00Z",
    algorithmVersion: "fixture-v1",
    hasChartData: false,
    operationalState: "READY",
    analysisErrorSession: null,
    analysisErrorCode: null,
  }],
};

const watchlistData = {
  count: 1,
  watchlistLimit: 20,
  remainingSlots: 19,
  items: [{
    instrumentId: 1,
    companyName: "Aurora Industries Limited",
    exchange: "NSE",
    tradingSymbol: "AURORA",
    marketDataState: "READY" as const,
    targetSession: "2026-07-24",
    addedAt: "2026-07-25T10:00:00Z",
    baselineSession: "2026-07-24",
    baselineClosePrice: "500.0000",
    latestClosePrice: "512.8000",
    movementSinceAddedPercent: "2.56",
  }],
};

const mockedUseSession = vi.mocked(useSession);
const mockedUseStocks = vi.mocked(useStocks);
const mockedUseWatchlist = vi.mocked(useWatchlist);
const mockedUseRemove = vi.mocked(useRemoveInstrument);
const mockedUseTechnical = vi.mocked(useFetchTechnicalData);
const mockedUseFundamental = vi.mocked(useFetchFundamentalData);
const mockedUseRerun = vi.mocked(useRerunBreakoutAlgorithm);
const mockedUseSearch = vi.mocked(useInstrumentSearch);
const mockedUseAdd = vi.mocked(useAddInstruments);

function renderStockList() {
  return render(<MemoryRouter><StockList /></MemoryRouter>);
}

function defaultMocks() {
  mockedUseSession.mockReturnValue({
    data: {
      authenticated: true,
      username: "mihir",
      role: "USER",
      watchlistLimit: 20,
      expiresAt: "2026-07-25T18:00:00Z",
    },
  } as ReturnType<typeof useSession>);
  mockedUseStocks.mockReturnValue({
    data: stockData,
    isPending: false,
    isError: false,
    isFetching: false,
    refetch: stockRefetch,
  } as unknown as ReturnType<typeof useStocks>);
  mockedUseWatchlist.mockReturnValue({
    data: watchlistData,
    isPending: false,
    isError: false,
    refetch: watchlistRefetch,
  } as unknown as ReturnType<typeof useWatchlist>);
  mockedUseRemove.mockReturnValue({
    isPending: false,
    isError: false,
    error: null,
    variables: undefined,
    mutate: removeMutate,
    reset: removeReset,
  } as unknown as ReturnType<typeof useRemoveInstrument>);
  mockedUseTechnical.mockReturnValue({
    isPending: false,
    isError: false,
    error: null,
    mutate: vi.fn(),
    reset: vi.fn(),
  } as unknown as ReturnType<typeof useFetchTechnicalData>);
  mockedUseFundamental.mockReturnValue({
    isPending: false,
    isError: false,
    error: null,
    mutate: vi.fn(),
    reset: vi.fn(),
  } as unknown as ReturnType<typeof useFetchFundamentalData>);
  mockedUseRerun.mockReturnValue({
    isPending: false,
    isError: false,
    error: null,
    mutate: vi.fn(),
    reset: vi.fn(),
  } as unknown as ReturnType<typeof useRerunBreakoutAlgorithm>);
  mockedUseSearch.mockImplementation((query) => ({
    data: query.length >= 2 ? {
      count: 1,
      items: [{
        companyName: "Reliance Industries Limited",
        exchange: "NSE",
        tradingSymbol: "RELIANCE",
        isin: "INE002A01018",
      }],
    } : undefined,
    isPending: false,
    isError: false,
    isSuccess: query.length >= 2,
  }) as ReturnType<typeof useInstrumentSearch>);
  mockedUseAdd.mockReturnValue({
    isPending: false,
    isError: false,
    error: null,
    mutateAsync: addMutateAsync,
    reset: addReset,
  } as unknown as ReturnType<typeof useAddInstruments>);
}

describe("StockList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    addMutateAsync.mockResolvedValue({
      activeCount: 2,
      watchlistLimit: 20,
      remainingSlots: 18,
    });
    defaultMocks();
  });

  it("announces that the personal watchlist is loading", () => {
    mockedUseStocks.mockReturnValue({
      data: undefined,
      isPending: true,
    } as unknown as ReturnType<typeof useStocks>);

    renderStockList();

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading your latest market research",
    );
  });

  it("shows setup-chart arrows only when immutable chart data exists", () => {
    mockedUseStocks.mockReturnValue({
      data: {
        ...stockData,
        items: [{
          ...stockData.items[0],
          technicalStatus: "CONSOLIDATING",
          algorithmVersion: "technical-v5",
          hasChartData: true,
        }],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      refetch: stockRefetch,
    } as unknown as ReturnType<typeof useStocks>);

    renderStockList();

    expect(screen.getAllByRole("button", {
      name: /Inspect setup chart for Aurora Industries Limited/i,
    })).toHaveLength(2);
  });

  it("shows early-recovery breakouts as a distinct technical status", () => {
    mockedUseStocks.mockReturnValue({
      data: {
        ...stockData,
        items: [{
          ...stockData.items[0],
          technicalStatus: "EARLY_RECOVERY_BREAKOUT",
        }],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      refetch: stockRefetch,
    } as unknown as ReturnType<typeof useStocks>);

    renderStockList();

    expect(screen.getAllByText("Early recovery")).toHaveLength(2);
  });

  it("shows active post-breakout holds as a distinct technical status", () => {
    mockedUseStocks.mockReturnValue({
      data: {
        ...stockData,
        items: [{
          ...stockData.items[0],
          technicalStatus: "BREAKOUT_HOLDING",
        }],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      refetch: stockRefetch,
    } as unknown as ReturnType<typeof useStocks>);

    renderStockList();

    expect(screen.getAllByText("Breakout holding")).toHaveLength(2);
  });

  it("keeps terminal analysis failures visible without unsafe detail links", () => {
    mockedUseStocks.mockReturnValue({
      data: {
        ...stockData,
        items: [{
          ...stockData.items[0],
          companyName: "New Listing Limited",
          tradingSymbol: "NEWLIST",
          analysisDate: null,
          technicalStatus: null,
          closePrice: null,
          dayChangePercent: null,
          source: null,
          sourceFetchedAt: null,
          algorithmVersion: null,
          operationalState: "ANALYSIS_FAILED",
          analysisErrorSession: "2026-07-29",
          analysisErrorCode: "INSUFFICIENT_LISTING_HISTORY",
        }],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      refetch: stockRefetch,
    } as unknown as ReturnType<typeof useStocks>);

    renderStockList();

    expect(screen.getAllByText("Insufficient history")).toHaveLength(2);
    expect(screen.getAllByText("Analysis unavailable").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Failed for 29 Jul 2026/)).toHaveLength(2);
    expect(screen.queryByRole("link", {
      name: "Open fundamental research for New Listing Limited",
    })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", {
      name: "Inspect setup chart for New Listing Limited",
    })).not.toBeInTheDocument();
  });

  it("retries membership and market results when loading fails", () => {
    mockedUseStocks.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch: stockRefetch,
    } as unknown as ReturnType<typeof useStocks>);

    renderStockList();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your watchlist is temporarily unavailable",
    );
    expect(stockRefetch).toHaveBeenCalledOnce();
    expect(watchlistRefetch).toHaveBeenCalledOnce();
  });

  it("opens a multi-select modal and saves selected ISINs as one batch", async () => {
    renderStockList();

    fireEvent.click(screen.getByRole("button", { name: "+ Add companies" }));
    expect(screen.getByRole("dialog", { name: "Add companies" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox", {
      name: "Search by company, symbol, or ISIN",
    }), {
      target: { value: "RELIANCE" },
    });
    const checkbox = await screen.findByRole("checkbox");
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Save (1)" }));

    await waitFor(() => {
      expect(addMutateAsync).toHaveBeenCalledWith(["INE002A01018"]);
    });
  });

  it("removes a stock through its three-dot action menu", () => {
    removeMutate.mockImplementation((_id, options) => options?.onSuccess?.());
    renderStockList();

    fireEvent.click(screen.getAllByRole("button", {
      name: "Actions for Aurora Industries Limited",
    })[0]);
    fireEvent.click(screen.getByRole("menuitem", { name: "Remove from watchlist" }));

    expect(removeMutate).toHaveBeenCalledWith(1, expect.any(Object));
    expect(screen.getByRole("status")).toHaveTextContent(
      "AURORA was removed from your watchlist",
    );
  });

  it("provides TradingView charts and plain-language market term help", () => {
    renderStockList();

    const chartLinks = screen.getAllByRole("link", {
      name: "Open Aurora Industries Limited chart on TradingView in a new tab",
    });
    expect(chartLinks).toHaveLength(2);
    expect(chartLinks[0]).toHaveAttribute(
      "href",
      "https://www.tradingview.com/chart/?symbol=NSE%3AAURORA",
    );
    expect(chartLinks[0]).toHaveAttribute("target", "_blank");
    expect(chartLinks[0]).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.queryByText("Breakout level")).not.toBeInTheDocument();
    expect(screen.getAllByText("Setup found").length).toBeGreaterThan(0);
  });

  it("opens fundamentals from the status arrow instead of the stock name", () => {
    renderStockList();

    const fundamentalLinks = screen.getAllByRole("link", {
      name: "Open fundamental research for Aurora Industries Limited",
    });
    expect(fundamentalLinks).toHaveLength(2);
    expect(fundamentalLinks[0]).toHaveAttribute("href", "/stocks/1");
    expect(screen.queryByRole("link", {
      name: "Aurora Industries Limited",
    })).not.toBeInTheDocument();
  });

  it("renders close, binary status, and quota responsively", () => {
    mockedUseWatchlist.mockReturnValue({
      data: {
        ...watchlistData,
        count: 2,
        remainingSlots: 18,
        items: [
          ...watchlistData.items,
          {
            instrumentId: 2,
            companyName: "Nexus Limited",
            exchange: "NSE",
            tradingSymbol: "NEXUS",
            marketDataState: "PREPARING",
            targetSession: "2026-07-24",
            addedAt: "2026-07-25T10:00:00Z",
            baselineSession: "2026-07-24",
            baselineClosePrice: null,
            latestClosePrice: null,
            movementSinceAddedPercent: null,
          },
        ],
      },
      isPending: false,
      isError: false,
      refetch: watchlistRefetch,
    } as unknown as ReturnType<typeof useWatchlist>);

    renderStockList();

    expect(screen.getByText("2 stocks of 20")).toBeInTheDocument();
    expect(screen.getByRole("table", {
      name: "Latest setup research for each stock",
    })).toBeInTheDocument();
    expect(screen.getAllByText("Setup found")).toHaveLength(2);
    expect(screen.queryByText("Nexus Limited")).not.toBeInTheDocument();
  });

  it("filters loaded table rows by company name or trading symbol", () => {
    const nexus = {
      ...stockData.items[0],
      instrumentId: 2,
      companyName: "Nexus Limited",
      tradingSymbol: "NEXUS",
    };
    mockedUseStocks.mockImplementation(({ search }) => {
      const all = [...stockData.items, nexus];
      const normalized = search.toLowerCase();
      const items = normalized
        ? all.filter((item) => (
            item.companyName.toLowerCase().includes(normalized)
            || item.tradingSymbol.toLowerCase().includes(normalized)
          ))
        : all;
      return {
        data: {
          ...stockData,
          count: items.length,
          items,
        },
        isPending: false,
        isError: false,
        isFetching: false,
        refetch: stockRefetch,
      } as unknown as ReturnType<typeof useStocks>;
    });

    renderStockList();
    const search = screen.getByRole("searchbox", { name: "Search your stocks" });

    fireEvent.change(search, { target: { value: "nExUs" } });

    expect(screen.getAllByText("Nexus Limited")).toHaveLength(2);
    expect(screen.queryByText("Aurora Industries Limited")).not.toBeInTheDocument();
    expect(screen.getByText("1 matching stock")).toBeInTheDocument();

    fireEvent.change(search, { target: { value: "aurora industries" } });

    expect(screen.getAllByText("Aurora Industries Limited")).toHaveLength(2);
    expect(screen.queryByText("Nexus Limited")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));

    expect(search).toHaveValue("");
    expect(screen.getAllByText("Aurora Industries Limited")).toHaveLength(2);
    expect(screen.getAllByText("Nexus Limited")).toHaveLength(2);
  });

  it("shows a clearable no-match state without changing the watchlist count", () => {
    mockedUseStocks.mockImplementation(({ search }) => ({
      data: search ? {
        ...stockData,
        count: 0,
        items: [],
        totalPages: 0,
      } : stockData,
      isPending: false,
      isError: false,
      isFetching: false,
      refetch: stockRefetch,
    }) as unknown as ReturnType<typeof useStocks>);
    renderStockList();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search your stocks" }), {
      target: { value: "missing" },
    });

    expect(screen.getByRole("heading", { name: "No matching stocks" })).toBeInTheDocument();
    expect(screen.getByText("1 stock of 20")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));

    expect(screen.getAllByText("Aurora Industries Limited")).toHaveLength(2);
  });

  it("requests the next server page for every signed-in role", () => {
    mockedUseStocks.mockReturnValue({
      data: {
        ...stockData,
        count: 55,
        totalPages: 2,
      },
      isPending: false,
      isError: false,
      isFetching: false,
      refetch: stockRefetch,
    } as unknown as ReturnType<typeof useStocks>);

    renderStockList();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(mockedUseStocks).toHaveBeenLastCalledWith({
      page: 2,
      search: "",
      sort: "status",
      pageSize: 50,
    });
  });

  it("changes server-side sorting and returns to the first page", () => {
    renderStockList();

    fireEvent.click(screen.getByRole("combobox", { name: "Sort by" }));
    fireEvent.click(screen.getByRole("option", { name: "1-day change: high to low" }));

    expect(mockedUseStocks).toHaveBeenLastCalledWith({
      page: 1,
      search: "",
      sort: "day_change_desc",
      pageSize: 50,
    });
  });

  it("changes page size and watchlist-return sorting on the server", () => {
    renderStockList();

    fireEvent.click(screen.getByRole("combobox", { name: "Rows" }));
    fireEvent.click(screen.getByRole("option", { name: "100" }));
    expect(mockedUseStocks).toHaveBeenLastCalledWith({
      page: 1,
      search: "",
      sort: "status",
      pageSize: 100,
    });

    fireEvent.click(screen.getByRole("combobox", { name: "Sort by" }));
    fireEvent.click(screen.getByRole("option", { name: "Since added: high to low" }));
    expect(mockedUseStocks).toHaveBeenLastCalledWith({
      page: 1,
      search: "",
      sort: "watchlist_change_desc",
      pageSize: 100,
    });
  });

  it("shows separate technical, fundamental, and algorithm controls to administrators", () => {
    mockedUseSession.mockReturnValue({
      data: {
        authenticated: true,
        username: "admin",
        role: "ADMIN",
        watchlistLimit: null,
        expiresAt: "2026-07-25T18:00:00Z",
      },
    } as ReturnType<typeof useSession>);

    renderStockList();

    expect(screen.getByRole("button", { name: "Fetch technical data" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fetch fundamental data" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Re-run algorithm" })).toBeInTheDocument();
  });

  it("announces terminal data-quality skips to administrators", () => {
    const technicalMutate = vi.fn((_variables, options) => options?.onSuccess?.({
      targetSession: "2026-07-27",
      scheduledCount: 0,
      alreadyUpdatingCount: 0,
      alreadyCurrentCount: 0,
      terminalDataFailureCount: 2,
    }));
    mockedUseSession.mockReturnValue({
      data: {
        authenticated: true,
        username: "admin",
        role: "ADMIN",
        watchlistLimit: null,
        expiresAt: "2026-07-25T18:00:00Z",
      },
    } as ReturnType<typeof useSession>);
    mockedUseTechnical.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      mutate: technicalMutate,
      reset: vi.fn(),
    } as unknown as ReturnType<typeof useFetchTechnicalData>);

    renderStockList();
    fireEvent.click(screen.getByRole("button", { name: "Fetch technical data" }));

    expect(screen.getByRole("status")).toHaveTextContent(
      "No duplicate jobs were queued; 2 stocks have terminal data-quality result for 2026-07-27.",
    );
  });

  it("warns administrators before globally deleting company data", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    removeMutate.mockImplementation((_id, options) => options?.onSuccess?.());
    mockedUseSession.mockReturnValue({
      data: {
        authenticated: true,
        username: "admin",
        role: "ADMIN",
        watchlistLimit: null,
        expiresAt: "2026-07-25T18:00:00Z",
      },
    } as ReturnType<typeof useSession>);

    renderStockList();
    fireEvent.click(screen.getAllByRole("button", {
      name: "Actions for Aurora Industries Limited",
    })[0]);
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete company data" }));

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("for every user"));
    expect(removeMutate).toHaveBeenCalledWith(1, expect.any(Object));
    expect(screen.getByRole("status")).toHaveTextContent(
      "AURORA and all of its stored data were deleted for every user",
    );
    confirm.mockRestore();
  });
});
