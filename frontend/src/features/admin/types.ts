export interface AdminAnalytics {
  generatedAt: string;
  users: {
    registeredUsers: number;
    newUsers7d: number;
    newUsers30d: number;
    activeUsers7d: number;
    activeUsers30d: number;
    telegramConnectedUsers: number;
  };
  stocks: {
    trackedStocks: number;
    activeWatchlistMemberships: number;
    averageStocksPerRegisteredUser: number;
    setupDistribution: Record<string, number>;
  };
  jobs: {
    pendingJobs: number;
    retryScheduledJobs: number;
    runningJobs: number;
    oldestPendingJobCreatedAt: string | null;
    latestAnalysisDate: string | null;
  };
}
