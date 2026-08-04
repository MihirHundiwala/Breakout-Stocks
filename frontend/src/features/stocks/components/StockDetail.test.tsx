import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useStockDetail } from "../hooks/useStockDetail";
import type { StockDetailData } from "../types";
import { StockDetail } from "./StockDetail";


vi.mock("../hooks/useStockDetail", () => ({ useStockDetail: vi.fn() }));

const detail: StockDetailData = {
  stock: {
    instrumentId: 7,
    companyName: "Reliance Industries Limited",
    exchange: "NSE",
    tradingSymbol: "RELIANCE",
    analysisDate: "2026-07-24",
    technicalStatus: "SETUP_FOUND",
    fundamentalCoverage: "COMPLETE",
    closePrice: "1500.25",
    dayChangePercent: "0.69",
    marketCapCrore: null,
    source: "UPSTOX",
    sourceFetchedAt: "2026-07-25T10:00:00Z",
    algorithmVersion: "technical-v1",
    hasChartData: false,
    operationalState: "READY",
    analysisErrorSession: null,
    analysisErrorCode: null,
  },
  fundamentals: {
    asOfDate: "2026-07-24",
    coverage: "COMPLETE",
    availableGroupCount: 6,
    expectedGroupCount: 6,
    metrics: {
      profile: { sector: "Refineries", description: "A diversified business." },
      ratios: { "P/E": { company_value: "20.15", sector_value: "12.46" } },
    },
    source: "UPSTOX",
    sourceFetchedAt: "2026-07-25T10:00:00Z",
    schemaVersion: "upstox-fundamentals-v1",
  },
  periods: [{
    periodEnd: "2025-03-31",
    periodKind: "YEARLY",
    statementBasis: "CONSOLIDATED",
    currency: "INR",
    metrics: { "income.revenue": "982671", "income.net_profit": "80787" },
    sourceFetchedAt: "2026-07-25T10:00:00Z",
    schemaVersion: "upstox-fundamentals-v1",
  }],
};

const mockedUseStockDetail = vi.mocked(useStockDetail);

function renderDetail() {
  render(
    <MemoryRouter initialEntries={["/stocks/7"]}>
      <Routes><Route path="/stocks/:instrumentId" element={<StockDetail />} /></Routes>
    </MemoryRouter>,
  );
}

describe("StockDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseStockDetail.mockReturnValue({
      data: detail,
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useStockDetail>);
  });

  it("shows setup context and company financial research", () => {
    renderDetail();

    expect(screen.getByRole("heading", { name: "Reliance Industries Limited" })).toBeInTheDocument();
    expect(screen.getByText("Setup found")).toBeInTheDocument();
    expect(screen.getByText("Refineries")).toBeInTheDocument();
    expect(screen.queryByText("Breakout level")).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Sector" })).toBeInTheDocument();
    expect(screen.getByText("9,82,671")).toBeInTheDocument();
  });

  it("explains unknown financial coverage without hiding setup status", () => {
    mockedUseStockDetail.mockReturnValue({
      data: { ...detail, fundamentals: null, periods: [] },
      isPending: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useStockDetail>);

    renderDetail();

    expect(screen.getByText(/Company financial data is not available yet/)).toBeInTheDocument();
    expect(screen.getByText("Setup found")).toBeInTheDocument();
    expect(screen.getByText("No statement periods are available.")).toBeInTheDocument();
  });
});
