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
  technicalStatus: "CONSOLIDATING",
  periodCount: 20,
  resistancePrice: "200.00",
  resistanceZoneLower: "199.40",
  resistanceZoneUpper: "200.60",
  resistanceTouchDates: ["2026-07-05", "2026-07-10", "2026-07-20"],
  candles: Array.from({ length: 20 }, (_, index) => ({
    date: `2026-07-${String(index + 1).padStart(2, "0")}`,
    open: "195.00",
    high: index === 4 ? "200.00" : index === 19 ? "202.00" : "198.00",
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
      technicalStatus: "BREAKOUT_HOLDING",
      periodCount: 30,
      resistancePrice: "205.00",
      resistanceZoneLower: "203.00",
      resistanceZoneUpper: "207.00",
      candles: dailyChart.candles.map((item, index) => ({
        ...item,
        high: index === 4 ? "205.00" : index === 19 ? "208.00" : item.high,
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
    expect(screen.getAllByRole("img", { name: /setup candlestick chart/i })).toHaveLength(1);
    expect(screen.getByText(/20 sessions/i)).toBeInTheDocument();
    expect(screen.getByText("Daily timeframe")).toBeInTheDocument();
    expect(screen.getByText("Consolidating")).toBeInTheDocument();
    expect(screen.getByText("Breakout holding")).toBeInTheDocument();
    expect(screen.getByText(/199.40–₹200.60/)).toBeInTheDocument();
    expect(screen.queryByText(/technical-v5/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/orange dots mark/i)).not.toBeInTheDocument();
    expect(screen.getAllByText(/^Threshold/i)).toHaveLength(1);
    expect(screen.getByText(/₹198.00/)).toBeInTheDocument();
    expect(screen.getByText(/1-day: \+1.02%/)).toBeInTheDocument();

    const breakoutThresholds = Array.from(container.querySelectorAll<SVGLineElement>(
      '[data-chart-role="breakout-threshold"]',
    ));
    const resistanceTouches = Array.from(
      container.querySelectorAll<SVGCircleElement>('[data-chart-role="resistance-touch"]'),
    );
    expect(breakoutThresholds).toHaveLength(1);
    expect(container.querySelectorAll('[data-chart-role="resistance-line"]')).toHaveLength(0);
    expect(resistanceTouches).toHaveLength(2);
    expect(resistanceTouches.every((touch) => touch.getAttribute("r") === "3")).toBe(true);
    expect(resistanceTouches.map((touch) => touch.dataset.price)).toEqual(["200", "200.6"]);
    expect(container.querySelector('[data-chart-role="setup-summary"]')).toBeInTheDocument();
    expect(screen.getByTestId("chart-modal-content")).toHaveClass("md:overflow-hidden");
    for (const chart of Array.from(container.querySelectorAll<SVGSVGElement>("svg"))) {
      expect(chart).toHaveClass("w-full");
      expect(chart).not.toHaveClass("min-w-[620px]");
      expect(chart.parentElement).toHaveClass("overflow-hidden");
      expect(chart.parentElement).not.toHaveClass("overflow-x-auto");
    }
    for (const touch of resistanceTouches) {
      const date = touch.dataset.date;
      const chart = touch.closest("svg");
      const wick = chart?.querySelector<SVGLineElement>(
        `[data-chart-role="candle-wick"][data-date="${date}"]`,
      );
      const breakoutThreshold = chart?.querySelector<SVGLineElement>(
        '[data-chart-role="breakout-threshold"]',
      );
      const resistanceZone = chart?.querySelector<SVGRectElement>(
        '[data-chart-role="resistance-zone"]',
      );
      expect(wick).not.toBeNull();
      expect(Number(touch.getAttribute("cy"))).toBeGreaterThanOrEqual(
        Number(breakoutThreshold?.getAttribute("y1")),
      );
      expect(Number(touch.getAttribute("cy"))).toBeLessThanOrEqual(
        Number(resistanceZone?.getAttribute("y"))
          + Number(resistanceZone?.getAttribute("height")),
      );
      if (Number(touch.dataset.price) < Number(dailyChart.resistanceZoneUpper)) {
        expect(touch.getAttribute("cy")).toBe(wick?.getAttribute("y1"));
      } else {
        expect(touch.getAttribute("cy")).toBe(breakoutThreshold?.getAttribute("y1"));
      }
    }

    const weeklyAxisLabels = Array.from(
      container.querySelectorAll<SVGTextElement>(
        '[data-chart-role="x-axis-label"]',
      ),
    ).filter((label) => label.textContent?.includes("2026"));
    expect(weeklyAxisLabels).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /Weekly.*breakout holding/i }));
    expect(screen.getAllByRole("img", { name: /weekly setup candlestick chart/i })).toHaveLength(1);
    expect(screen.getByText(/30 weeks/i)).toBeInTheDocument();
    expect(screen.getByText("Weekly timeframe")).toBeInTheDocument();
    expect(screen.queryByText("Daily timeframe")).not.toBeInTheDocument();
    expect(
      container.querySelectorAll<SVGCircleElement>('[data-chart-role="resistance-touch"]'),
    ).toHaveLength(2);
    expect(
      Array.from(container.querySelectorAll<SVGCircleElement>('[data-chart-role="resistance-touch"]'))
        .map((touch) => touch.dataset.price),
    ).toEqual(["205", "207"]);
    const selectedWeeklyAxisLabels = Array.from(
      container.querySelectorAll<SVGTextElement>('[data-chart-role="x-axis-label"]'),
    ).filter((label) => label.textContent?.includes("2026"));
    expect(selectedWeeklyAxisLabels).toHaveLength(4);

    fireEvent.click(screen.getByRole("button", { name: "Close setup chart" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
