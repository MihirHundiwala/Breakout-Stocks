import { describe, expect, it } from "vitest";

import { readCookieValue } from "./client";


describe("readCookieValue", () => {
  it("reads and decodes only the requested cookie", () => {
    expect(
      readCookieValue(
        "breakout_csrf",
        "theme=dark; breakout_csrf=token%20value; other=value",
      ),
    ).toBe("token value");
  });

  it("returns null for missing or malformed cookie values", () => {
    expect(readCookieValue("breakout_csrf", "theme=dark")).toBeNull();
    expect(
      readCookieValue("breakout_csrf", "breakout_csrf=%E0%A4%A"),
    ).toBeNull();
  });
});
