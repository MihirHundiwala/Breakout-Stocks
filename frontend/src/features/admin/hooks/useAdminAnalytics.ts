import { useQuery } from "@tanstack/react-query";

import { getAdminAnalytics } from "../api/analytics";


export function useAdminAnalytics() {
  return useQuery({
    queryKey: ["admin", "analytics"],
    queryFn: getAdminAnalytics,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false,
  });
}
