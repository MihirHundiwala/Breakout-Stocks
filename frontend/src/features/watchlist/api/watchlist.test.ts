import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../../api/client";
import {
  WatchlistApiError,
  addInstruments,
  getWatchlist,
  removeInstrument,
  searchInstruments,
} from "./watchlist";


vi.mock("../../../api/client", () => ({
  apiClient: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedDelete = vi.mocked(apiClient.delete);
const mockedGet = vi.mocked(apiClient.get);
const mockedPost = vi.mocked(apiClient.post);

function axiosError(status: number, detail: unknown) {
  return {
    isAxiosError: true,
    response: { status, data: { detail } },
  };
}

describe("personal watchlist API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("maps personal membership and capacity fields", async () => {
    mockedGet.mockResolvedValue({
      data: {
        items: [{
          instrument_id: 1,
          company_name: "Aurora Engineering Limited",
          exchange: "NSE",
          trading_symbol: "AURORA",
          market_data_state: "PREPARING",
          target_session: "2026-07-24",
          added_at: "2026-07-25T10:00:00Z",
          baseline_session: "2026-07-24",
          baseline_close_price: "500.0000",
          latest_close_price: "512.8000",
          movement_since_added_percent: "2.56",
        }],
        count: 1,
        watchlist_limit: 20,
        remaining_slots: 19,
      },
    });

    await expect(getWatchlist()).resolves.toEqual({
      items: [{
        instrumentId: 1,
        companyName: "Aurora Engineering Limited",
        exchange: "NSE",
        tradingSymbol: "AURORA",
        marketDataState: "PREPARING",
        targetSession: "2026-07-24",
        addedAt: "2026-07-25T10:00:00Z",
        baselineSession: "2026-07-24",
        baselineClosePrice: "500.0000",
        latestClosePrice: "512.8000",
        movementSinceAddedPercent: "2.56",
      }],
      count: 1,
      watchlistLimit: 20,
      remainingSlots: 19,
    });
    expect(mockedGet).toHaveBeenCalledWith("/watchlist/instruments");
  });

  it("submits all selected ISINs in one batch", async () => {
    mockedPost.mockResolvedValue({
      data: {
        active_count: 2,
        watchlist_limit: 20,
        remaining_slots: 18,
      },
    });

    await expect(
      addInstruments(["INE002A01018", "INE123A01016"]),
    ).resolves.toMatchObject({ activeCount: 2, remainingSlots: 18 });
    expect(mockedPost).toHaveBeenCalledWith("/watchlist/instruments", {
      isins: ["INE002A01018", "INE123A01016"],
    });
  });

  it("maps a quota conflict with its configured limit", async () => {
    mockedPost.mockRejectedValue(
      axiosError(409, {
        code: "WATCHLIST_LIMIT_EXCEEDED",
        limit: 20,
        active_count: 19,
        requested_count: 2,
      }),
    );

    await expect(addInstruments(["INE002A01018"])).rejects.toEqual(
      new WatchlistApiError("WATCHLIST_LIMIT_EXCEEDED", 20),
    );
  });

  it("maps personal removal capacity", async () => {
    mockedDelete.mockResolvedValue({
      data: {
        instrument_id: 1,
        removed: true,
        active_count: 4,
        watchlist_limit: 20,
        remaining_slots: 16,
      },
    });

    await expect(removeInstrument(1)).resolves.toEqual({
      instrumentId: 1,
      activeCount: 4,
      watchlistLimit: 20,
      remainingSlots: 16,
    });
    expect(mockedDelete).toHaveBeenCalledWith("/watchlist/instruments/1");
  });

  it("maps expired authentication without exposing response details", async () => {
    mockedGet.mockRejectedValue(axiosError(401, "AUTHENTICATION_REQUIRED"));

    await expect(getWatchlist()).rejects.toEqual(
      new WatchlistApiError("AUTHENTICATION_REQUIRED"),
    );
  });

  it("uses the signed-in company-search endpoint", async () => {
    mockedGet.mockResolvedValue({
      data: {
        items: [{
          company_name: "Reliance Industries Limited",
          exchange: "NSE",
          trading_symbol: "RELIANCE",
          isin: "INE002A01018",
        }],
        count: 1,
      },
    });

    await expect(searchInstruments("RELIANCE")).resolves.toMatchObject({
      count: 1,
      items: [{ tradingSymbol: "RELIANCE" }],
    });
    expect(mockedGet).toHaveBeenCalledWith(
      "/watchlist/instruments/search",
      { params: { query: "RELIANCE" } },
    );
  });
});
