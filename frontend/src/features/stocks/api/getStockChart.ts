import { apiClient } from "../../../api/client";
import type {
  AnalysisChartCandle,
  AnalysisChartData,
  AnalysisChartsData,
  TechnicalStatus,
} from "../types";


interface AnalysisChartSlideResponse {
  timeframe: "DAILY" | "WEEKLY";
  period_count: number;
  resistance_price: string;
  resistance_zone_lower: string;
  resistance_zone_upper: string;
  resistance_touch_dates: string[];
  candles: AnalysisChartCandle[];
  schema_version: string;
}

interface AnalysisChartResponse {
  instrument_id: number;
  company_name: string;
  trading_symbol: string;
  analysis_date: string;
  technical_status: TechnicalStatus;
  charts: AnalysisChartSlideResponse[];
}

export async function getStockChart(
  instrumentId: number,
): Promise<AnalysisChartsData> {
  const { data } = await apiClient.get<AnalysisChartResponse>(
    `/stocks/${instrumentId}/chart`,
  );
  return {
    instrumentId: data.instrument_id,
    companyName: data.company_name,
    tradingSymbol: data.trading_symbol,
    analysisDate: data.analysis_date,
    technicalStatus: data.technical_status,
    charts: data.charts.map((chart): AnalysisChartData => ({
      timeframe: chart.timeframe,
      periodCount: chart.period_count,
      resistancePrice: chart.resistance_price,
      resistanceZoneLower: chart.resistance_zone_lower,
      resistanceZoneUpper: chart.resistance_zone_upper,
      resistanceTouchDates: chart.resistance_touch_dates,
      candles: chart.candles,
      schemaVersion: chart.schema_version,
    })),
  };
}
