export type MarketDataState = "PREPARING" | "READY" | "ANALYSIS_FAILED";

export interface WatchlistItem {
  instrumentId: number;
  companyName: string;
  exchange: string;
  tradingSymbol: string;
  marketDataState: MarketDataState;
  targetSession: string;
  addedAt: string;
  baselineSession: string;
  baselineClosePrice: string | null;
  latestClosePrice: string | null;
  movementSinceAddedPercent: string | null;
}

export interface WatchlistData {
  items: WatchlistItem[];
  count: number;
  watchlistLimit: number | null;
  remainingSlots: number | null;
}

export interface InstrumentCandidate {
  companyName: string;
  exchange: string;
  tradingSymbol: string;
  isin: string;
}

export interface InstrumentSearchData {
  items: InstrumentCandidate[];
  count: number;
}

export interface BatchAddResult {
  activeCount: number;
  watchlistLimit: number | null;
  remainingSlots: number | null;
}

export interface RemoveInstrumentResult {
  instrumentId: number;
  activeCount: number;
  watchlistLimit: number | null;
  remainingSlots: number | null;
}

export interface RefreshResearchResult {
  targetSession: string;
  scheduledCount: number;
  alreadyUpdatingCount: number;
  alreadyCurrentCount: number;
  terminalDataFailureCount: number;
}
