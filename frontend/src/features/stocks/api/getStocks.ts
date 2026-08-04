import { apiClient } from "../../../api/client";
import type {
  FundamentalCoverageStatus,
  StockListData,
  StockListItem,
  StockPageSize,
  StockSort,
  TechnicalStatus,
  TrackingOperationalState,
} from "../types";


interface StockListItemResponse {
  instrument_id: number;
  company_name: string;
  exchange: string;
  trading_symbol: string;
  analysis_date: string | null;
  technical_status: TechnicalStatus | null;
  fundamental_coverage: FundamentalCoverageStatus;
  close_price: string | null;
  day_change_percent: string | null;
  market_cap_crore: string | null;
  source: string | null;
  source_fetched_at: string | null;
  algorithm_version: string | null;
  has_chart_data: boolean;
  operational_state: TrackingOperationalState;
  analysis_error_session: string | null;
  analysis_error_code: string | null;
}

interface StockListResponse {
  items: StockListItemResponse[];
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface StockListRequest {
  page: number;
  search: string;
  sort: StockSort;
  pageSize: StockPageSize;
}

export function mapStockListItem(
  response: StockListItemResponse,
): StockListItem {
  return {
    instrumentId: response.instrument_id,
    companyName: response.company_name,
    exchange: response.exchange,
    tradingSymbol: response.trading_symbol,
    analysisDate: response.analysis_date,
    technicalStatus: response.technical_status,
    fundamentalCoverage: response.fundamental_coverage,
    closePrice: response.close_price,
    dayChangePercent: response.day_change_percent,
    marketCapCrore: response.market_cap_crore,
    source: response.source,
    sourceFetchedAt: response.source_fetched_at,
    algorithmVersion: response.algorithm_version,
    hasChartData: response.has_chart_data,
    operationalState: response.operational_state,
    analysisErrorSession: response.analysis_error_session,
    analysisErrorCode: response.analysis_error_code,
  };
}

export async function getStocks({
  page,
  search,
  sort,
  pageSize,
}: StockListRequest): Promise<StockListData> {
  const response =
    await apiClient.get<StockListResponse>("/stocks", {
      params: {
        page,
        sort,
        page_size: pageSize,
        ...(search ? { search } : {}),
      },
    });

  return {
    items: response.data.items.map(mapStockListItem),
    count: response.data.count,
    page: response.data.page,
    pageSize: response.data.page_size,
    totalPages: response.data.total_pages,
  };
}
