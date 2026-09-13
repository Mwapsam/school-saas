"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";

import { ApiError } from "@/lib/api";
import { Toaster } from "@/components/ui/sonner";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Keep data fresh for 5 minutes — avoids redundant refetches for
        // stable data like classes, announcements, and marksheets.
        staleTime: 5 * 60 * 1000,
        // Hold unused cache entries for 10 minutes before GC.
        gcTime: 10 * 60 * 1000,
        // Never retry auth errors — a 401 means the token is gone and apiFetch
        // has already attempted a refresh. Retrying just floods the server with
        // more 401s while the session-expiry redirect is in flight.
        retry: (failureCount, error) => {
          if (error instanceof ApiError && error.status === 401) return false;
          return failureCount < 1;
        },
        refetchOnWindowFocus: false,
        retryOnMount: true,
      },
    },
  });
}

export function Providers({ children }: { children: React.ReactNode }) {
  // useState ensures the QueryClient is not recreated on every render while
  // also keeping it isolated per request in SSR scenarios.
  const [client] = useState(makeQueryClient);

  return (
    // defaultTheme="light" avoids a flash of dark/system theme on first paint.
    // Users can still toggle to dark via the ThemeToggle.
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      <QueryClientProvider client={client}>
        {children}
        <Toaster richColors position="top-right" />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
