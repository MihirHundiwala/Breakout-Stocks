import axios from "axios";
import { useEffect } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";

import { sessionQueryKey } from "../../auth/hooks/useAuth";
import { getStocks } from "../api/getStocks";
import type { StockPageSize, StockSort } from "../types";


export const stocksQueryKey = ["stocks", "list"] as const;

export function useStocks({
  page,
  search,
  sort,
  pageSize,
}: {
  page: number;
  search: string;
  sort: StockSort;
  pageSize: StockPageSize;
}) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: [...stocksQueryKey, { page, search, sort, pageSize }],
    queryFn: () => getStocks({ page, search, sort, pageSize }),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
    refetchInterval: 15_000,
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
