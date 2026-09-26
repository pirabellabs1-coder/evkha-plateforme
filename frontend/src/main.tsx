import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { router } from "./router";
import "./theme/tokens.css";
import "./theme/espace.css";
import "./viz/viz.css";
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
      {/* Plus d'enveloppe `<Theme>` Radix : chaque écran porte la charte
          (`theme/tokens.css`, `theme/espace.css`), et ce que l'enveloppe
          donnait en héritage — police, encre, interligne, taille de base,
          fond — est posé sur `body` par `index.css`. */}
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
);
