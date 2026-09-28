"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { Icon } from "@/components/icon";
import { clearWorkspaceDraftFromStorage } from "@/lib/workspace-draft-storage";

export interface WorkspaceErrorBoundaryProps {
  readonly children: ReactNode;
}

interface WorkspaceErrorBoundaryState {
  readonly hasError: boolean;
  readonly errorMessage: string | null;
}

export class WorkspaceErrorBoundary extends Component<
  WorkspaceErrorBoundaryProps,
  WorkspaceErrorBoundaryState
> {
  constructor(props: WorkspaceErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, errorMessage: null };
  }

  static getDerivedStateFromError(error: Error): WorkspaceErrorBoundaryState {
    return {
      hasError: true,
      errorMessage: error.message || "An unexpected workspace error occurred.",
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    if (process.env.NODE_ENV !== "production") {
      console.error("WorkspaceErrorBoundary caught an error:", error, errorInfo);
    }
  }

  handleReload = () => {
    if (typeof window !== "undefined") {
      window.location.reload();
    }
  };

  handleStartFresh = () => {
    clearWorkspaceDraftFromStorage();
    if (typeof window !== "undefined") {
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <main className="workspace-error-fallback" role="alert">
          <div className="error-card">
            <span className="error-card-icon">
              <Icon name="help" />
            </span>
            <h2>Workspace encountered an error</h2>
            <p className="error-description">
              {this.state.errorMessage ||
                "A map or interface rendering error prevented the workspace from displaying."}
            </p>
            <div className="error-actions">
              <button type="button" className="button button-quiet" onClick={this.handleReload}>
                Reload Workspace
              </button>
              <button
                type="button"
                className="button button-primary"
                onClick={this.handleStartFresh}
              >
                Start Fresh (Clear Draft)
              </button>
            </div>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}
