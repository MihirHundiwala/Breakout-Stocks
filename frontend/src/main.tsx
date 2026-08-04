import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { BrowserRouter } from "react-router";

import { App } from "./App";
import "./index.css";


const queryClient = new QueryClient();

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Unable to find the React root element.");
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
