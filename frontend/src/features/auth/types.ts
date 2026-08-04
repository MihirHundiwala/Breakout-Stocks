export type UserRole = "ADMIN" | "USER";

export interface Session {
  authenticated: true;
  username: string;
  role: UserRole;
  watchlistLimit: number | null;
  expiresAt: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export type SignupCredentials = LoginCredentials;
