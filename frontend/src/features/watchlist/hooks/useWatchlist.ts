import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { sessionQueryKey } from "../../auth/hooks/useAuth";
import { stocksQueryKey } from "../../stocks/hooks/useStocks";
import {
  addInstruments,
  fetchFundamentalData,
  fetchTechnicalData,
  getWatchlist,
  rerunBreakoutAlgorithm,
  removeInstrument,
  searchInstruments,
  WatchlistApiError,
} from "../api/watchlist";


export const watchlistQueryKey = ["watchlist"] as const;
export const instrumentSearchQueryKey = (query: string) => [
  "instruments",
  "search",
  query,
] as const;

function isExpiredSession(error: unknown): boolean {
  return error instanceof WatchlistApiError && error.code === "AUTHENTICATION_REQUIRED";
}

function useSessionExpiry(error: unknown) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (isExpiredSession(error)) {
      queryClient.setQueryData(sessionQueryKey, null);
    }
  }, [error, queryClient]);
}

export function useWatchlist() {
  const query = useQuery({
    queryKey: watchlistQueryKey,
    queryFn: getWatchlist,
    retry: false,
  });
  useSessionExpiry(query.error);
  return query;
}

export function useInstrumentSearch(query: string, enabled: boolean) {
  return useQuery({
    queryKey: instrumentSearchQueryKey(query),
    queryFn: () => searchInstruments(query),
    enabled: enabled && query.length >= 2,
    retry: false,
    staleTime: 60_000,
  });
}

function invalidateWatchlist(queryClient: ReturnType<typeof useQueryClient>) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: watchlistQueryKey }),
    queryClient.invalidateQueries({ queryKey: stocksQueryKey }),
  ]);
}

export function useAddInstruments() {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: addInstruments,
    onSuccess: () => invalidateWatchlist(queryClient),
    onError: (error) => {
      if (isExpiredSession(error)) queryClient.setQueryData(sessionQueryKey, null);
    },
  });
  return mutation;
}

export function useRemoveInstrument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: removeInstrument,
    onSuccess: () => invalidateWatchlist(queryClient),
    onError: (error) => {
      if (isExpiredSession(error)) queryClient.setQueryData(sessionQueryKey, null);
    },
  });
}

export function useFetchTechnicalData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fetchTechnicalData,
    onSuccess: () => invalidateWatchlist(queryClient),
    onError: (error) => {
      if (isExpiredSession(error)) queryClient.setQueryData(sessionQueryKey, null);
    },
  });
}

export function useFetchFundamentalData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fetchFundamentalData,
    onSuccess: () => invalidateWatchlist(queryClient),
    onError: (error) => {
      if (isExpiredSession(error)) queryClient.setQueryData(sessionQueryKey, null);
    },
  });
}

export function useRerunBreakoutAlgorithm() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: rerunBreakoutAlgorithm,
    onSuccess: () => invalidateWatchlist(queryClient),
    onError: (error) => {
      if (isExpiredSession(error)) queryClient.setQueryData(sessionQueryKey, null);
    },
  });
}
