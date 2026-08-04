import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";

import { useLogin, useSession, useSignup } from "../hooks/useAuth";
import { LoginPage } from "./LoginPage";
import { RequireAuth } from "./RequireAuth";
import { SignupPage } from "./SignupPage";


vi.mock("../hooks/useAuth", () => ({
  useLogin: vi.fn(),
  useSession: vi.fn(),
  useSignup: vi.fn(),
}));

const mockedUseLogin = vi.mocked(useLogin);
const mockedUseSession = vi.mocked(useSession);
const mockedUseSignup = vi.mocked(useSignup);
const mutateAsync = vi.fn();
const signupMutateAsync = vi.fn();

function signedOutSession() {
  mockedUseSession.mockReturnValue({
    data: null,
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof useSession>);
}

describe("authentication routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    signedOutSession();
    mockedUseLogin.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      mutateAsync,
      reset: vi.fn(),
    } as unknown as ReturnType<typeof useLogin>);
    mockedUseSignup.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      mutateAsync: signupMutateAsync,
      reset: vi.fn(),
    } as unknown as ReturnType<typeof useSignup>);
  });

  it("submits normalized credentials from the separate login page", async () => {
    mutateAsync.mockResolvedValue({});
    render(<MemoryRouter initialEntries={["/login"]}><LoginPage /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "  mihir  " },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        username: "mihir",
        password: "secret-password",
      });
    });
  });

  it("redirects an already authenticated user away from login", () => {
    mockedUseSession.mockReturnValue({
      data: {
        authenticated: true,
        username: "admin",
        role: "ADMIN",
        watchlistLimit: null,
        expiresAt: "2026-07-25T18:00:00Z",
      },
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof useSession>);

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<h1>Personal watchlist</h1>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Personal watchlist" })).toBeInTheDocument();
  });

  it("redirects a signed-out user from protected pages to login", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/login" element={<h1>Login destination</h1>} />
          <Route element={<RequireAuth />}>
            <Route path="/" element={<h1>Private watchlist</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Login destination" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Private watchlist" })).not.toBeInTheDocument();
  });

  it("submits a matching password from the signup page", async () => {
    signupMutateAsync.mockResolvedValue({});
    render(<MemoryRouter initialEntries={["/signup"]}><SignupPage /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "  new.investor  " },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "a-secure-test-password" },
    });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "a-secure-test-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(signupMutateAsync).toHaveBeenCalledWith({
        username: "new.investor",
        password: "a-secure-test-password",
      });
    });
  });

  it("stops signup locally when the passwords differ", async () => {
    render(<MemoryRouter initialEntries={["/signup"]}><SignupPage /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "new.investor" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "a-secure-test-password" },
    });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "a-different-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("passwords do not match");
    expect(signupMutateAsync).not.toHaveBeenCalled();
  });
});
