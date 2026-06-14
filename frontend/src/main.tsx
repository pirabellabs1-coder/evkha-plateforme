import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { Theme } from "@radix-ui/themes";
import "@radix-ui/themes/styles.css";
import { router } from "./router";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 1,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Theme accentColor="orange" grayColor="sand" radius="medium" panelBackground="solid">
        <RouterProvider router={router} />
      </Theme>
    </QueryClientProvider>
  </StrictMode>
);
