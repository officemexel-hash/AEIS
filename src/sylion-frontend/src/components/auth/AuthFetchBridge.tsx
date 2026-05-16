"use client";

import { useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const PATCH_FLAG = "__aeisAuthFetchPatched";
const TOKEN_KEY = "aeis_auth_token_id";

function shouldAttachAuth(url: string): boolean {
  return (API_BASE ? url.startsWith(API_BASE) : false) || url.startsWith("/api/");
}

function headersWithAuth(initHeaders: HeadersInit | undefined, token: string): Headers {
  const headers = new Headers(initHeaders || {});
  if (!headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

export function AuthFetchBridge() {
  useEffect(() => {
    const win = window as typeof window & {
      [PATCH_FLAG]?: boolean;
      __aeisOriginalFetch?: typeof window.fetch;
    };
    if (win[PATCH_FLAG]) return;

    const originalFetch = window.fetch.bind(window);
    win.__aeisOriginalFetch = originalFetch;
    win[PATCH_FLAG] = true;

    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;
      const token = window.localStorage.getItem(TOKEN_KEY);
      if (!token || !shouldAttachAuth(url)) {
        return originalFetch(input, init);
      }

      if (input instanceof Request) {
        const headers = headersWithAuth(input.headers, token);
        const request = new Request(input, { headers });
        return originalFetch(request, init);
      }

      return originalFetch(input, {
        ...init,
        headers: headersWithAuth(init?.headers, token),
      });
    };
  }, []);

  return null;
}
