import axios from "axios";

import { apiClient } from "../../../api/client";
import type { LoginCredentials, Session, SignupCredentials, UserRole } from "../types";


interface SessionApiResponse {
  authenticated: true;
  username: string;
  role: UserRole;
  watchlist_limit: number | null;
  expires_at: string;
}

interface ApiErrorResponse {
  detail?: string;
}

export type AuthErrorCode =
  | "AUTH_NOT_CONFIGURED"
  | "CSRF_VALIDATION_FAILED"
  | "INVALID_CREDENTIALS"
  | "PASSWORD_TOO_SHORT"
  | "USERNAME_UNAVAILABLE"
  | "UNAVAILABLE";

export class AuthError extends Error {
  constructor(public readonly code: AuthErrorCode) {
    super(code);
    this.name = "AuthError";
  }
}

function mapSession(response: SessionApiResponse): Session {
  return {
    authenticated: response.authenticated,
    username: response.username,
    role: response.role,
    watchlistLimit: response.watchlist_limit,
    expiresAt: response.expires_at,
  };
}

function authError(error: unknown): AuthError {
  if (axios.isAxiosError<ApiErrorResponse>(error)) {
    const detail = error.response?.data?.detail;
    if (
      detail === "AUTH_NOT_CONFIGURED" ||
      detail === "CSRF_VALIDATION_FAILED" ||
      detail === "INVALID_CREDENTIALS" ||
      detail === "PASSWORD_TOO_SHORT" ||
      detail === "USERNAME_UNAVAILABLE"
    ) {
      return new AuthError(detail);
    }
  }
  return new AuthError("UNAVAILABLE");
}

export async function getSession(): Promise<Session | null> {
  try {
    const response = await apiClient.get<SessionApiResponse>("/auth/session");
    return mapSession(response.data);
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      return null;
    }
    throw authError(error);
  }
}

export async function login(credentials: LoginCredentials): Promise<Session> {
  try {
    const response = await apiClient.post<SessionApiResponse>(
      "/auth/login",
      credentials,
    );
    return mapSession(response.data);
  } catch (error) {
    throw authError(error);
  }
}

export async function signup(credentials: SignupCredentials): Promise<Session> {
  try {
    const response = await apiClient.post<SessionApiResponse>(
      "/auth/signup",
      credentials,
    );
    return mapSession(response.data);
  } catch (error) {
    throw authError(error);
  }
}

export async function logout(): Promise<void> {
  try {
    await apiClient.post("/auth/logout");
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) return;
    throw authError(error);
  }
}
