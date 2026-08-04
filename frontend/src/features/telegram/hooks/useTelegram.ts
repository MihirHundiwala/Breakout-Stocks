import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { connectTelegram, getTelegramConnection } from "../api/telegram";

export const telegramConnectionQueryKey = ["telegram-connection"] as const;

export function useTelegramConnection() {
  return useQuery({
    queryKey: telegramConnectionQueryKey,
    queryFn: getTelegramConnection,
    staleTime: 10_000,
    refetchInterval: (query) => query.state.data?.pending ? 2_000 : false,
  });
}

export function useConnectTelegram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: connectTelegram,
    onSuccess: (result) => queryClient.setQueryData(telegramConnectionQueryKey, result),
  });
}
