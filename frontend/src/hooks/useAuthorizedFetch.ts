import { useCallback } from "react";
import { useAuth } from "@/auth/AuthProvider";

type FetchInput = RequestInfo | URL;
export function useAuthorizedFetch() {
  const { acquireToken } = useAuth();

  return useCallback(
    async (input: FetchInput, init?: RequestInit) => {
      const token = await acquireToken();

      if (!token) {
        throw new Error("Authentication required to call this resource.");
      }

      const headers = new Headers(init?.headers);
      headers.set("Authorization", `Bearer ${token}`);

      return fetch(input, {
        ...init,
        headers,
      });
    },
    [acquireToken]
  );
}
