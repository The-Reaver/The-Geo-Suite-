"use client";

import { useEffect } from "react";
import { registerNovaServiceWorker } from "./lib/registerServiceWorker";

/** Mount-only registration, rendered from layout.tsx. Renders nothing. */
export default function ServiceWorkerRegister() {
  useEffect(() => {
    registerNovaServiceWorker();
  }, []);
  return null;
}
