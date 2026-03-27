"use client";
import { useEffect } from "react";

export default function NgrokInterceptor() {
  useEffect(() => {
    if (typeof window !== "undefined") {
      const originalFetch = window.fetch;
      window.fetch = async function (...args) {
        let [resource, config] = args;
        if (typeof resource === "string" && resource.includes("ngrok")) {
          config = config || {};
          config.headers = {
            ...config.headers,
            "ngrok-skip-browser-warning": "69420",
          };
          return originalFetch(resource, config as RequestInit);
        }
        return originalFetch(...args);
      };
    }
  }, []);
  return null;
}
