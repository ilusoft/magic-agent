import { useCallback } from "react";
import { useAuth } from "@/auth/AuthProvider";

type FetchInput = RequestInfo | URL;
type AuthorizedRequestInit = RequestInit & {
  includeAuth?: boolean;
};

export function useAuthorizedFetch() {
  const { acquireToken } = useAuth();

  return useCallback(
    async (input: FetchInput, init?: AuthorizedRequestInit) => {
      const includeAuth = init?.includeAuth ?? true;
      const headers = new Headers(init?.headers ?? {});

      if (includeAuth) {
        const token = await acquireToken();

        if (!token) {
          throw new Error("Authentication required to call this resource.");
        }

        headers.set("Authorization", `Bearer ${token}`);
      }

      if (!headers.has("Accept")) {
        headers.set("Accept", "application/json");
      }

      const shouldSetJsonContentType =
        typeof init?.body === "string" &&
        init.body.length > 0 &&
        !headers.has("Content-Type");

      if (shouldSetJsonContentType) {
        headers.set("Content-Type", "application/json");
      }

      const { includeAuth: _omit, ...restInit } = init ?? {};

      return fetch(input, {
        ...restInit,
        mode: restInit.mode ?? "cors",
        credentials: restInit.credentials ?? "include",
        headers,
      });
    },
    [acquireToken]
  );
}
