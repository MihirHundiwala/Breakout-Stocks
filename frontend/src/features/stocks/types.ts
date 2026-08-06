export type TechnicalStatus =
  | "NO_SETUP"
  | "CONSOLIDATING"
  | "RETEST"
  // Historical values remain accepted while v1-v3 snapshots are readable.
  | "FORMING"
  | "READY"
  | "BREAKOUT"
  | "EARLY_RECOVERY_BREAKOUT"
  | "WEAK_BREAKOUT"
  | "BREAKOUT_HOLDING"
  | "FAILED_BREAKOUT"
  | "SETUP_FOUND";

export type FundamentalCoverageStatus =
  | "UNKNOWN"
  | "PARTIAL"
  | "COMPLETE";

export type TrackingOperationalState =
  | "PREPARING"
  | "READY"
  | "ANALYSIS_FAILED";

export type StockSort =
  | "status"
  | "market_cap_desc"
  | "market_cap_asc"
  | "day_change_desc"
  | "day_change_asc"
  | "watchlist_change_desc"
  | "watchlist_change_asc";

export type StockPageSize = 10 | 25 | 50 | 100 | "all";

export interface StockListItem {
  instrumentId: number;
  companyName: string;
  exchange: string;
  tradingSymbol: string;
  analysisDate: string | null;
  technicalStatus: TechnicalStatus | null;
  fundamentalCoverage: FundamentalCoverageStatus;
  closePrice: string | null;
  dayChangePercent: string | null;
  marketCapCrore: string | null;
  source: string | null;
  sourceFetchedAt: string | null;
  algorithmVersion: string | null;
  hasChartData: boolean;
  operationalState: TrackingOperationalState;
  analysisErrorSession: string | null;
  analysisErrorCode: string | null;
}

export interface AnalysisChartCandle {
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
}

export interface AnalysisChartData {
  timeframe: "DAILY" | "WEEKLY";
  technicalStatus: TechnicalStatus;
  periodCount: number;
  resistancePrice: string;
  resistanceZoneLower: string;
  resistanceZoneUpper: string;
  resistanceTouchDates: string[];
  candles: AnalysisChartCandle[];
  schemaVersion: string;
}

export interface AnalysisChartsData {
  instrumentId: number;
  companyName: string;
  tradingSymbol: string;
  analysisDate: string;
  technicalStatus: TechnicalStatus;
  charts: AnalysisChartData[];
}

export interface StockListData {
  items: StockListItem[];
  count: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface FundamentalSnapshotDetail {
  asOfDate: string;
  coverage: FundamentalCoverageStatus;
  availableGroupCount: number;
  expectedGroupCount: number;
  metrics: Record<string, JsonValue>;
  source: string;
  sourceFetchedAt: string;
  schemaVersion: string;
}

export interface FundamentalPeriodDetail {
  periodEnd: string;
  periodKind: string;
  statementBasis: string;
  currency: string;
  metrics: Record<string, JsonValue>;
  sourceFetchedAt: string;
  schemaVersion: string;
}

export interface StockDetailData {
  stock: StockListItem;
  fundamentals: FundamentalSnapshotDetail | null;
  periods: FundamentalPeriodDetail[];
}
