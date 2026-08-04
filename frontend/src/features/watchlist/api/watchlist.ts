import axios from "axios";

import { apiClient } from "../../../api/client";
import type {
  BatchAddResult,
  InstrumentSearchData,
  MarketDataState,
  RefreshResearchResult,
  RemoveInstrumentResult,
  WatchlistData,
} from "../types";


interface WatchlistResponse {
  items: Array<{
    instrument_id: number;
    company_name: string;
    exchange: string;
    trading_symbol: string;
    market_data_state: MarketDataState;
    target_session: string;
    added_at: string;
    baseline_session: string;
    baseline_close_price: string | null;
    latest_close_price: string | null;
    movement_since_added_percent: string | null;
  }>;
  count: number;
  watchlist_limit: number | null;
  remaining_slots: number | null;
}

interface InstrumentSearchResponse {
  items: Array<{
    company_name: string;
    exchange: string;
    trading_symbol: string;
    isin: string;
  }>;
  count: number;
}

interface BatchAddResponse {
  active_count: number;
  watchlist_limit: number | null;
  remaining_slots: number | null;
}

interface RemoveInstrumentResponse {
  instrument_id: number;
  active_count: number;
  watchlist_limit: number | null;
  remaining_slots: number | null;
}

interface RefreshResearchResponse {
  target_session: string;
  scheduled_count: number;
  already_updating_count: number;
  already_current_count: number;
  terminal_data_failure_count: number;
}

interface LimitErrorDetail {
  code: "WATCHLIST_LIMIT_EXCEEDED";
  limit: number;
  active_count: number;
  requested_count: number;
}

interface ApiErrorResponse {
  detail?: string | LimitErrorDetail;
}

export type WatchlistApiErrorCode =
  | "AUTHENTICATION_REQUIRED"
  | "CSRF_VALIDATION_FAILED"
  | "WATCHLIST_ITEM_NOT_FOUND"
  | "WATCHLIST_LIMIT_EXCEEDED"
  | "UPSTOX_INSTRUMENT_NOT_FOUND"
  | "INSTRUMENT_IDENTITY_UNRESOLVED"
  | "MARKET_DATA_NOT_CONFIGURED"
  | "MARKET_DATA_AUTH_FAILED"
  | "MARKET_DATA_RATE_LIMITED"
  | "MARKET_DATA_UNAVAILABLE"
  | "UNAVAILABLE";

export class WatchlistApiError extends Error {
  constructor(
    public readonly code: WatchlistApiErrorCode,
    public readonly limit: number | null = null,
  ) {
    super(code);
    this.name = "WatchlistApiError";
  }
}

function watchlistError(error: unknown): WatchlistApiError {
  if (axios.isAxiosError<ApiErrorResponse>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "object" && detail?.code === "WATCHLIST_LIMIT_EXCEEDED") {
      return new WatchlistApiError(detail.code, detail.limit);
    }
    if (
      detail === "AUTHENTICATION_REQUIRED" ||
      detail === "CSRF_VALIDATION_FAILED" ||
      detail === "WATCHLIST_ITEM_NOT_FOUND" ||
      detail === "UPSTOX_INSTRUMENT_NOT_FOUND" ||
      detail === "INSTRUMENT_IDENTITY_UNRESOLVED" ||
      detail === "MARKET_DATA_NOT_CONFIGURED" ||
      detail === "MARKET_DATA_AUTH_FAILED" ||
      detail === "MARKET_DATA_RATE_LIMITED" ||
      detail === "MARKET_DATA_UNAVAILABLE"
    ) {
      return new WatchlistApiError(detail);
    }
  }
  return new WatchlistApiError("UNAVAILABLE");
}

export async function getWatchlist(): Promise<WatchlistData> {
  try {
    const response = await apiClient.get<WatchlistResponse>("/watchlist/instruments");
    return {
      items: response.data.items.map((item) => ({
        instrumentId: item.instrument_id,
        companyName: item.company_name,
        exchange: item.exchange,
        tradingSymbol: item.trading_symbol,
        marketDataState: item.market_data_state,
        targetSession: item.target_session,
        addedAt: item.added_at,
        baselineSession: item.baseline_session,
        baselineClosePrice: item.baseline_close_price,
        latestClosePrice: item.latest_close_price,
        movementSinceAddedPercent: item.movement_since_added_percent,
      })),
      count: response.data.count,
      watchlistLimit: response.data.watchlist_limit,
      remainingSlots: response.data.remaining_slots,
    };
  } catch (error) {
    throw watchlistError(error);
  }
}

export async function searchInstruments(query: string): Promise<InstrumentSearchData> {
  try {
    const response = await apiClient.get<InstrumentSearchResponse>(
      "/watchlist/instruments/search",
      { params: { query } },
    );
    return {
      items: response.data.items.map((item) => ({
        companyName: item.company_name,
        exchange: item.exchange,
        tradingSymbol: item.trading_symbol,
        isin: item.isin,
      })),
      count: response.data.count,
    };
  } catch (error) {
    throw watchlistError(error);
  }
}

export async function addInstruments(isins: string[]): Promise<BatchAddResult> {
  try {
    const response = await apiClient.post<BatchAddResponse>(
      "/watchlist/instruments",
      { isins },
    );
    return {
      activeCount: response.data.active_count,
      watchlistLimit: response.data.watchlist_limit,
      remainingSlots: response.data.remaining_slots,
    };
  } catch (error) {
    throw watchlistError(error);
  }
}

export async function removeInstrument(
  instrumentId: number,
): Promise<RemoveInstrumentResult> {
  try {
    const response = await apiClient.delete<RemoveInstrumentResponse>(
      `/watchlist/instruments/${instrumentId}`,
    );
    return {
      instrumentId: response.data.instrument_id,
      activeCount: response.data.active_count,
      watchlistLimit: response.data.watchlist_limit,
      remainingSlots: response.data.remaining_slots,
    };
  } catch (error) {
    throw watchlistError(error);
  }
}

export async function fetchTechnicalData(): Promise<RefreshResearchResult> {
  try {
    const response = await apiClient.post<RefreshResearchResponse>(
      "/admin/watchlist/instruments/refresh",
    );
    return {
      targetSession: response.data.target_session,
      scheduledCount: response.data.scheduled_count,
      alreadyUpdatingCount: response.data.already_updating_count,
      alreadyCurrentCount: response.data.already_current_count,
      terminalDataFailureCount: response.data.terminal_data_failure_count,
    };
  } catch (error) {
    throw watchlistError(error);
  }
}

export async function fetchFundamentalData(): Promise<RefreshResearchResult> {
  try {
    const response = await apiClient.post<RefreshResearchResponse>(
      "/admin/watchlist/instruments/refresh-fundamentals",
    );
    return {
      targetSession: response.data.target_session,
      scheduledCount: response.data.scheduled_count,
      alreadyUpdatingCount: response.data.already_updating_count,
      alreadyCurrentCount: response.data.already_current_count,
      terminalDataFailureCount: response.data.terminal_data_failure_count,
    };
  } catch (error) {
    throw watchlistError(error);
  }
}

export async function rerunBreakoutAlgorithm(): Promise<RefreshResearchResult> {
  try {
    const response = await apiClient.post<RefreshResearchResponse>(
      "/admin/watchlist/instruments/rerun-algorithm",
    );
    return {
      targetSession: response.data.target_session,
      scheduledCount: response.data.scheduled_count,
      alreadyUpdatingCount: response.data.already_updating_count,
      alreadyCurrentCount: response.data.already_current_count,
      terminalDataFailureCount: response.data.terminal_data_failure_count,
    };
  } catch (error) {
    throw watchlistError(error);
  }
}
