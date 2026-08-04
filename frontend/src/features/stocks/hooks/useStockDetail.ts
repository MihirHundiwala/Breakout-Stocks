import axios from "axios";
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { sessionQueryKey } from "../../auth/hooks/useAuth";
import { getStockDetail } from "../api/getStockDetail";


export function useStockDetail(instrumentId: number | null) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["stocks", "detail", instrumentId],
    queryFn: () => getStockDetail(instrumentId as number),
    enabled: instrumentId !== null,
    staleTime: 5 * 60_000,
    retry: (failureCount, error) =>
      !(axios.isAxiosError(error) && error.response?.status === 401) &&
      failureCount < 1,
  });
  useEffect(() => {
    if (axios.isAxiosError(query.error) && query.error.response?.status === 401) {
      queryClient.setQueryData(sessionQueryKey, null);
    }
  }, [query.error, queryClient]);
  return query;
}
