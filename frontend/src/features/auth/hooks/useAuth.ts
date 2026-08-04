import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getSession, login, logout, signup } from "../api/auth";


export const sessionQueryKey = ["session"] as const;

export function useSession() {
  return useQuery({
    queryKey: sessionQueryKey,
    queryFn: getSession,
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: login,
    onSuccess: (session) => {
      queryClient.setQueryData(sessionQueryKey, session);
    },
  });
}

export function useSignup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: signup,
    onSuccess: (session) => {
      queryClient.setQueryData(sessionQueryKey, session);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.clear();
      queryClient.setQueryData(sessionQueryKey, null);
    },
  });
}
