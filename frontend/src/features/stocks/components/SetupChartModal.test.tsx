import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useStockChart } from "../hooks/useStockChart";
import type {
  AnalysisChartData,
  AnalysisChartsData,
  StockListItem,
} from "../types";
import { SetupChartModal } from "./SetupChartModal";


vi.mock("../hooks/useStockChart", () => ({ useStockChart: vi.fn() }));

const stock: StockListItem = {
  instrumentId: 7,
  companyName: "Aurora Industries Limited",
  exchange: "NSE",
  tradingSymbol: "AURORA",
  analysisDate: "2026-07-28",
  technicalStatus: "CONSOLIDATING",
  fundamentalCoverage: "UNKNOWN",
  closePrice: "198.00",
  dayChangePercent: "1.00",
  marketCapCrore: "2500",
  source: "UPSTOX",
  sourceFetchedAt: "2026-07-28T12:00:00Z",
  algorithmVersion: "technical-v5",
  hasChartData: true,
  operationalState: "READY",
  analysisErrorSession: null,
  analysisErrorCode: null,
};

const dailyChart: AnalysisChartData = {
  timeframe: "DAILY",
  periodCount: 20,
  resistancePrice: "200.00",
  resistanceZoneLower: "199.40",
  resistanceZoneUpper: "200.60",
  resistanceTouchDates: ["2026-07-05", "2026-07-20"],
  candles: Array.from({ length: 20 }, (_, index) => ({
    date: `2026-07-${String(index + 1).padStart(2, "0")}`,
    open: "195.00",
    high: index === 4 || index === 19 ? "200.00" : "198.00",
    low: "193.00",
    close: index === 19 ? "198.00" : "196.00",
    volume: 1000 + index * 10,
  })),
  schemaVersion: "technical-chart-v2",
};

const chartData: AnalysisChartsData = {
  instrumentId: 7,
  companyName: stock.companyName,
  tradingSymbol: stock.tradingSymbol,
  analysisDate: "2026-07-28",
  technicalStatus: "CONSOLIDATING",
  charts: [
    dailyChart,
    {
      ...dailyChart,
      timeframe: "WEEKLY",
      periodCount: 30,
      resistancePrice: "205.00",
      resistanceZoneLower: "203.00",
      resistanceZoneUpper: "207.00",
      candles: dailyChart.candles.map((item, index) => ({
        ...item,
        close: index === 19 ? "205.00" : index === 18 ? "200.00" : item.close,
      })),
    },
  ],
};

const mockedUseStockChart = vi.mocked(useStockChart);

describe("SetupChartModal", () => {
  it("renders fitted candle evidence and closes accessibly", () => {
    const onClose = vi.fn();
    mockedUseStockChart.mockReturnValue({
      data: chartData,
      isPending: false,
      isError: false,
    } as ReturnType<typeof useStockChart>);

    const { container } = render(<SetupChartModal stock={stock} onClose={onClose} />);

    expect(screen.getByRole("dialog")).toHaveTextContent(stock.companyName);
    expect(screen.getByRole("img", { name: /setup candlestick chart/i })).toBeInTheDocument();
    expect(screen.getByText(/20 sessions/i)).toBeInTheDocument();
    expect(screen.getByText(/199.40–₹200.60/)).toBeInTheDocument();
    expect(screen.queryByText(/technical-v5/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/orange dots mark/i)).not.toBeInTheDocument();
    expect(screen.getByText(/breakout threshold/i)).toBeInTheDocument();
    expect(screen.getByText(/₹198.00/)).toBeInTheDocument();
    expect(screen.getByText(/1-day: \+1.02%/)).toBeInTheDocument();

    const breakoutThreshold = container.querySelector<SVGLineElement>(
      '[data-chart-role="breakout-threshold"]',
    );
    const resistanceTouches = Array.from(
      container.querySelectorAll<SVGCircleElement>('[data-chart-role="resistance-touch"]'),
    );
    expect(breakoutThreshold).not.toBeNull();
    expect(resistanceTouches).toHaveLength(2);
    for (const touch of resistanceTouches) {
      const date = touch.dataset.date;
      const wick = container.querySelector<SVGLineElement>(
        `[data-chart-role="candle-wick"][data-date="${date}"]`,
      );
      expect(wick).not.toBeNull();
      expect(touch.getAttribute("cy")).toBe(wick?.getAttribute("y1"));
      expect(touch.getAttribute("cy")).not.toBe(breakoutThreshold?.getAttribute("y1"));
    }

    fireEvent.click(screen.getByRole("button", { name: "Next setup chart" }));
    expect(screen.getByText("Weekly long base")).toBeInTheDocument();
    expect(screen.getByText(/30 weeks/i)).toBeInTheDocument();
    expect(screen.getByText("2 of 2")).toBeInTheDocument();
    expect(screen.getByText(/₹205.00/)).toBeInTheDocument();
    expect(screen.getByText(/This week: \+2.50%/)).toBeInTheDocument();
    const weeklyAxisLabels = Array.from(
      container.querySelectorAll<SVGTextElement>(
        '[data-chart-role="x-axis-label"]',
      ),
    );
    expect(weeklyAxisLabels).toHaveLength(4);
    expect(weeklyAxisLabels.every((label) => label.textContent?.includes("2026"))).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Close setup chart" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
