import { useQuery } from "@tanstack/react-query";

import { getStockChart } from "../api/getStockChart";


export function useStockChart(instrumentId: number | null) {
  return useQuery({
    queryKey: ["stocks", "chart", instrumentId],
    queryFn: () => getStockChart(instrumentId as number),
    enabled: instrumentId !== null,
    staleTime: 30 * 60_000,
    retry: 1,
  });
}
