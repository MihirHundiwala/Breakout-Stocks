import { apiClient } from "../../../api/client";
import { mapStockListItem } from "./getStocks";
import type {
  FundamentalCoverageStatus,
  JsonValue,
  StockDetailData,
  TechnicalStatus,
  TrackingOperationalState,
} from "../types";


interface StockItemResponse {
  instrument_id: number;
  company_name: string;
  exchange: string;
  trading_symbol: string;
  analysis_date: string;
  technical_status: TechnicalStatus;
  fundamental_coverage: FundamentalCoverageStatus;
  close_price: string;
  day_change_percent: string;
  market_cap_crore: string | null;
  source: string;
  source_fetched_at: string;
  algorithm_version: string;
  has_chart_data: boolean;
  operational_state: TrackingOperationalState;
  analysis_error_session: string | null;
  analysis_error_code: string | null;
}

interface FundamentalSnapshotResponse {
  as_of_date: string;
  coverage: FundamentalCoverageStatus;
  available_group_count: number;
  expected_group_count: number;
  metrics: Record<string, JsonValue>;
  source: string;
  source_fetched_at: string;
  schema_version: string;
}

interface FundamentalPeriodResponse {
  period_end: string;
  period_kind: string;
  statement_basis: string;
  currency: string;
  metrics: Record<string, JsonValue>;
  source_fetched_at: string;
  schema_version: string;
}

interface StockDetailResponse {
  stock: StockItemResponse;
  fundamentals: FundamentalSnapshotResponse | null;
  periods: FundamentalPeriodResponse[];
}

export async function getStockDetail(instrumentId: number): Promise<StockDetailData> {
  if (!Number.isSafeInteger(instrumentId) || instrumentId < 1) {
    throw new Error("A positive instrument ID is required.");
  }
  const { data } = await apiClient.get<StockDetailResponse>(
    `/stocks/${instrumentId}`,
  );
  return {
    stock: mapStockListItem(data.stock),
    fundamentals: data.fundamentals === null
      ? null
      : {
          asOfDate: data.fundamentals.as_of_date,
          coverage: data.fundamentals.coverage,
          availableGroupCount: data.fundamentals.available_group_count,
          expectedGroupCount: data.fundamentals.expected_group_count,
          metrics: data.fundamentals.metrics,
          source: data.fundamentals.source,
          sourceFetchedAt: data.fundamentals.source_fetched_at,
          schemaVersion: data.fundamentals.schema_version,
        },
    periods: data.periods.map((period) => ({
      periodEnd: period.period_end,
      periodKind: period.period_kind,
      statementBasis: period.statement_basis,
      currency: period.currency,
      metrics: period.metrics,
      sourceFetchedAt: period.source_fetched_at,
      schemaVersion: period.schema_version,
    })),
  };
}
