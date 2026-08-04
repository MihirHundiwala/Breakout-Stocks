import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../../api/client";
import { getAdminAnalytics } from "./analytics";


vi.mock("../../../api/client", () => ({
  apiClient: { get: vi.fn() },
}));

const mockedGet = vi.mocked(apiClient.get);

describe("admin analytics API", () => {
  beforeEach(() => vi.clearAllMocks());

  it("maps aggregate fields and decimal averages", async () => {
    mockedGet.mockResolvedValue({
      data: {
        generated_at: "2026-08-01T09:00:00Z",
        users: {
          registered_users: 12,
          new_users_7d: 2,
          new_users_30d: 4,
          active_users_7d: 7,
          active_users_30d: 10,
          telegram_connected_users: 6,
        },
        stocks: {
          tracked_stocks: 25,
          active_watchlist_memberships: 60,
          average_stocks_per_registered_user: "5.00",
          setup_distribution: { CONSOLIDATING: 8, BREAKOUT: 3 },
        },
        jobs: {
          pending_jobs: 2,
          retry_scheduled_jobs: 1,
          running_jobs: 3,
          oldest_pending_job_created_at: "2026-08-01T08:00:00Z",
          latest_analysis_date: "2026-07-31",
        },
      },
    });

    const result = await getAdminAnalytics();

    expect(mockedGet).toHaveBeenCalledWith("/admin/analytics");
    expect(result.users.activeUsers7d).toBe(7);
    expect(result.stocks.averageStocksPerRegisteredUser).toBe(5);
    expect(result.stocks.setupDistribution.BREAKOUT).toBe(3);
    expect(result.jobs.retryScheduledJobs).toBe(1);
  });
});
