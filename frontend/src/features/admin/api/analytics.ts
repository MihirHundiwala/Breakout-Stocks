import { apiClient } from "../../../api/client";
import type { AdminAnalytics } from "../types";


interface AnalyticsResponse {
  generated_at: string;
  users: {
    registered_users: number;
    new_users_7d: number;
    new_users_30d: number;
    active_users_7d: number;
    active_users_30d: number;
    telegram_connected_users: number;
  };
  stocks: {
    tracked_stocks: number;
    active_watchlist_memberships: number;
    average_stocks_per_registered_user: string;
    setup_distribution: Record<string, number>;
  };
  jobs: {
    pending_jobs: number;
    retry_scheduled_jobs: number;
    running_jobs: number;
    oldest_pending_job_created_at: string | null;
    latest_analysis_date: string | null;
  };
}


export async function getAdminAnalytics(): Promise<AdminAnalytics> {
  const { data } = await apiClient.get<AnalyticsResponse>("/admin/analytics");
  return {
    generatedAt: data.generated_at,
    users: {
      registeredUsers: data.users.registered_users,
      newUsers7d: data.users.new_users_7d,
      newUsers30d: data.users.new_users_30d,
      activeUsers7d: data.users.active_users_7d,
      activeUsers30d: data.users.active_users_30d,
      telegramConnectedUsers: data.users.telegram_connected_users,
    },
    stocks: {
      trackedStocks: data.stocks.tracked_stocks,
      activeWatchlistMemberships: data.stocks.active_watchlist_memberships,
      averageStocksPerRegisteredUser: Number(
        data.stocks.average_stocks_per_registered_user,
      ),
      setupDistribution: data.stocks.setup_distribution,
    },
    jobs: {
      pendingJobs: data.jobs.pending_jobs,
      retryScheduledJobs: data.jobs.retry_scheduled_jobs,
      runningJobs: data.jobs.running_jobs,
      oldestPendingJobCreatedAt: data.jobs.oldest_pending_job_created_at,
      latestAnalysisDate: data.jobs.latest_analysis_date,
    },
  };
}
