import axios from "axios";


const CSRF_COOKIE_NAME = "breakout_csrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const MUTATING_METHODS = new Set(["DELETE", "PATCH", "POST", "PUT"]);


export function readCookieValue(
  name: string,
  cookieSource: string = document.cookie,
): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  const cookie = cookieSource
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));

  if (!cookie) {
    return null;
  }

  try {
    return decodeURIComponent(cookie.slice(prefix.length));
  } catch {
    return null;
  }
}


export const apiClient = axios.create({
  baseURL: "/api",
  timeout: 10_000,
  withCredentials: true,
  headers: {
    Accept: "application/json",
  },
});


apiClient.interceptors.request.use((config) => {
  const method = config.method?.toUpperCase();
  if (!method || !MUTATING_METHODS.has(method)) {
    return config;
  }

  const csrfToken = readCookieValue(CSRF_COOKIE_NAME);
  if (csrfToken) {
    config.headers.set(CSRF_HEADER_NAME, csrfToken);
  }
  return config;
});
