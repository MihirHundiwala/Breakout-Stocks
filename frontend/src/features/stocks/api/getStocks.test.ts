import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../../api/client";
import { getStocks } from "./getStocks";


vi.mock("../../../api/client", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const mockedGet = vi.mocked(apiClient.get);

describe("stock list API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends search before pagination and maps page metadata", async () => {
    mockedGet.mockResolvedValue({
      data: {
        items: [],
        count: 55,
        page: 2,
        page_size: 50,
        total_pages: 2,
      },
    });

    const result = await getStocks({
      page: 2,
      search: "reliance",
      sort: "market_cap_desc",
      pageSize: 25,
    });

    expect(mockedGet).toHaveBeenCalledWith("/stocks", {
      params: {
        page: 2,
        search: "reliance",
        sort: "market_cap_desc",
        page_size: 25,
      },
    });
    expect(result).toEqual({
      items: [],
      count: 55,
      page: 2,
      pageSize: 50,
      totalPages: 2,
    });
  });

  it("omits an empty search parameter", async () => {
    mockedGet.mockResolvedValue({
      data: {
        items: [],
        count: 0,
        page: 1,
        page_size: 50,
        total_pages: 0,
      },
    });

    await getStocks({
      page: 1,
      search: "",
      sort: "status",
      pageSize: "all",
    });

    expect(mockedGet).toHaveBeenCalledWith("/stocks", {
      params: { page: 1, sort: "status", page_size: "all" },
    });
  });

  it("maps a terminal analysis failure without inventing market results", async () => {
    mockedGet.mockResolvedValue({
      data: {
        items: [{
          instrument_id: 9,
          company_name: "New Listing Limited",
          exchange: "NSE",
          trading_symbol: "NEWLIST",
          analysis_date: null,
          technical_status: null,
          fundamental_coverage: "UNKNOWN",
          close_price: null,
          day_change_percent: null,
          market_cap_crore: "1200",
          source: null,
          source_fetched_at: null,
          algorithm_version: null,
          has_chart_data: false,
          operational_state: "ANALYSIS_FAILED",
          analysis_error_session: "2026-07-29",
          analysis_error_code: "INSUFFICIENT_LISTING_HISTORY",
        }],
        count: 1,
        page: 1,
        page_size: 50,
        total_pages: 1,
      },
    });

    const result = await getStocks({
      page: 1,
      search: "",
      sort: "status",
      pageSize: 50,
    });

    expect(result.items[0]).toMatchObject({
      technicalStatus: null,
      closePrice: null,
      operationalState: "ANALYSIS_FAILED",
      analysisErrorSession: "2026-07-29",
      analysisErrorCode: "INSUFFICIENT_LISTING_HISTORY",
    });
  });
});
