import { useQuery } from "@tanstack/react-query";

import { getReadiness } from "../api/getReadiness";


export const readinessQueryKey = ["system", "readiness"] as const;

export function useReadiness() {
  return useQuery({
    queryKey: readinessQueryKey,
    queryFn: getReadiness,
    staleTime: 10_000,
    refetchInterval: 30_000,
    retry: 1,
  });
}
