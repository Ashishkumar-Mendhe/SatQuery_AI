"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiClientError,
  apiBaseUrl,
  type BackendHealth,
  inspectBackendHealth,
} from "@/lib/health-client";

type ViewState =
  | { state: "checking" }
  | { state: "result"; result: BackendHealth }
  | { state: "unreachable"; detail: string; requestId: string | null }
  | { state: "unexpected"; detail: string; requestId: string | null };

function diagnosticsUrl(): string {
  try {
    return apiBaseUrl();
  } catch {
    return "not configured";
  }
}

export function ServiceStatus({
  showDiagnostics = false,
  compact = false,
}: {
  showDiagnostics?: boolean;
  compact?: boolean;
}) {
  const [view, setView] = useState<ViewState>({ state: "checking" });
  const activeRequest = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setView({ state: "checking" });

    try {
      const result = await inspectBackendHealth({ signal: controller.signal });
      if (!controller.signal.aborted) setView({ state: "result", result });
    } catch (error) {
      if (controller.signal.aborted) return;
      if (error instanceof ApiClientError) {
        const state = ["network", "timeout"].includes(error.kind) ? "unreachable" : "unexpected";
        setView({ state, detail: error.message, requestId: error.requestId });
        return;
      }
      setView({
        state: "unexpected",
        detail: "The health request failed unexpectedly.",
        requestId: null,
      });
    }
  }, []);

  useEffect(() => {
    void refresh();
    return () => activeRequest.current?.abort();
  }, [refresh]);

  let title = "Checking backend readiness";
  let compactTitle = "Checking backend";
  let detail = "Requesting live service state…";
  let tone = "";
  let requestId: string | null = null;

  if (view.state === "result" && view.result.state === "ready") {
    title = "Backend reachable and ready";
    compactTitle = "Backend ready";
    detail = "PostgreSQL, PostGIS, and the migration revision are current.";
    tone = "ready";
    requestId = view.result.requestId;
  } else if (view.state === "result" && view.result.state === "database_unavailable") {
    title = "Backend reachable; database unavailable";
    compactTitle = "Database unavailable";
    detail = view.result.message;
    tone = "warning";
    requestId = view.result.requestId;
  } else if (view.state === "unreachable") {
    title = "Backend unreachable";
    compactTitle = "Backend unreachable";
    detail = view.detail;
    tone = "error";
    requestId = view.requestId;
  } else if (view.state === "unexpected") {
    title = "Unexpected response or request failure";
    compactTitle = "Connection error";
    detail = view.detail;
    tone = "error";
    requestId = view.requestId;
  }

  return (
    <section
      className={`status-panel ${compact ? "status-panel-compact" : ""}`}
      aria-label="Service connection status"
      aria-live="polite"
      data-service-state={view.state === "result" ? view.result.state : view.state}
    >
      <div className="status-row">
        <span className={`status-dot ${tone}`} aria-hidden="true" />
        <p className="status-title">{compact ? compactTitle : title}</p>
      </div>
      <p className="status-detail">{detail}</p>
      {showDiagnostics ? (
        <p className="diagnostics">
          API: {diagnosticsUrl()}
          {requestId ? ` · Request: ${requestId}` : ""}
        </p>
      ) : null}
      <button
        className="retry-button"
        type="button"
        onClick={() => void refresh()}
        disabled={view.state === "checking"}
      >
        {view.state === "checking" ? "Checking…" : compact ? "Retry" : "Retry status check"}
      </button>
    </section>
  );
}
