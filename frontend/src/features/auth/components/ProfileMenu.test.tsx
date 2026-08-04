import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";

import { useLogout } from "../hooks/useAuth";
import { useConnectTelegram, useTelegramConnection } from "../../telegram/hooks/useTelegram";
import { ProfileMenu } from "./ProfileMenu";


vi.mock("../hooks/useAuth", () => ({ useLogout: vi.fn() }));
vi.mock("../../telegram/hooks/useTelegram", () => ({
  useConnectTelegram: vi.fn(),
  useTelegramConnection: vi.fn(),
}));

const session = {
  authenticated: true as const,
  username: "mihir",
  role: "ADMIN" as const,
  watchlistLimit: null,
  expiresAt: "2026-07-31T12:00:00Z",
};
const connectMutate = vi.fn();
const telegramWindow = {
  close: vi.fn(),
  location: { href: "" },
  opener: window,
};

describe("ProfileMenu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    telegramWindow.location.href = "";
    telegramWindow.opener = window;
    vi.spyOn(window, "open").mockReturnValue(
      telegramWindow as unknown as Window,
    );
    vi.mocked(useLogout).mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
    } as unknown as ReturnType<typeof useLogout>);
    vi.mocked(useConnectTelegram).mockReturnValue({
      isPending: false,
      isError: false,
      mutate: connectMutate,
    } as unknown as ReturnType<typeof useConnectTelegram>);
  });

  it("offers direct Telegram connection when available", () => {
    vi.mocked(useTelegramConnection).mockReturnValue({
      data: { available: true, connected: false, pending: false, username: null },
    } as unknown as ReturnType<typeof useTelegramConnection>);

    render(<MemoryRouter><ProfileMenu session={session} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Open profile menu" }));
    fireEvent.click(screen.getByRole("button", { name: "Connect" }));

    expect(connectMutate).toHaveBeenCalledTimes(1);
    const callbacks = connectMutate.mock.calls[0]?.[1];
    callbacks.onSuccess({ botUrl: "https://t.me/example_bot?start=token" });
    expect(telegramWindow.location.href).toBe(
      "https://t.me/example_bot?start=token",
    );
    expect(telegramWindow.opener).toBeNull();
    expect(screen.getByRole("menu")).toHaveTextContent("Log out");
  });

  it("shows verified connected state instead of a connect button", () => {
    vi.mocked(useTelegramConnection).mockReturnValue({
      data: { available: true, connected: true, pending: false, username: "marketwatcher" },
    } as unknown as ReturnType<typeof useTelegramConnection>);

    render(<MemoryRouter><ProfileMenu session={session} /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Open profile menu" }));

    expect(screen.getByText("Connected as @marketwatcher")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Connect" })).not.toBeInTheDocument();
  });
});
