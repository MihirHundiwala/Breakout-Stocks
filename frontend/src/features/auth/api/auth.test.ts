import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../../api/client";
import {
  AuthError,
  getSession,
  login,
  logout,
  signup,
} from "./auth";


vi.mock("../../../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));


const mockedGet = vi.mocked(apiClient.get);
const mockedPost = vi.mocked(apiClient.post);


function axiosError(status: number, detail?: string) {
  return {
    isAxiosError: true,
    response: {
      status,
      data: { detail },
    },
  };
}


describe("auth API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("maps the backend session response to frontend names", async () => {
    mockedGet.mockResolvedValue({
      data: {
        authenticated: true,
        username: "mihir",
        role: "USER",
        watchlist_limit: 20,
        expires_at: "2026-07-25T18:00:00Z",
      },
    });

    await expect(getSession()).resolves.toEqual({
      authenticated: true,
      username: "mihir",
      role: "USER",
      watchlistLimit: 20,
      expiresAt: "2026-07-25T18:00:00Z",
    });
  });

  it("treats an unauthenticated session lookup as a visitor", async () => {
    mockedGet.mockRejectedValue(axiosError(401));

    await expect(getSession()).resolves.toBeNull();
  });

  it("maps invalid login credentials to a safe typed error", async () => {
    mockedPost.mockRejectedValue(
      axiosError(401, "INVALID_CREDENTIALS"),
    );

    await expect(
      login({ username: "mihir", password: "wrong" }),
    ).rejects.toEqual(new AuthError("INVALID_CREDENTIALS"));
  });

  it("treats logout of an expired session as completed", async () => {
    mockedPost.mockRejectedValue(axiosError(401));

    await expect(logout()).resolves.toBeUndefined();
  });

  it("creates an account and maps its authenticated session", async () => {
    mockedPost.mockResolvedValue({
      data: {
        authenticated: true,
        username: "new.investor",
        role: "USER",
        watchlist_limit: 20,
        expires_at: "2026-07-25T18:00:00Z",
      },
    });

    await expect(signup({
      username: "new.investor",
      password: "a-secure-test-password",
    })).resolves.toMatchObject({
      username: "new.investor",
      role: "USER",
      watchlistLimit: 20,
    });
    expect(mockedPost).toHaveBeenCalledWith("/auth/signup", {
      username: "new.investor",
      password: "a-secure-test-password",
    });
  });

  it("maps an unavailable signup username to a safe typed error", async () => {
    mockedPost.mockRejectedValue(axiosError(409, "USERNAME_UNAVAILABLE"));

    await expect(signup({
      username: "admin",
      password: "a-secure-test-password",
    })).rejects.toEqual(new AuthError("USERNAME_UNAVAILABLE"));
  });
});
