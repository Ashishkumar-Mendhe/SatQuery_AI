"use client";

import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";
import { Icon } from "@/components/icon";
import { ServiceStatus } from "@/components/service-status";
import { getDataOriginDisplay } from "@/lib/data-origin";
import type { DataOrigin } from "@/lib/provider-contracts";

export function WorkspaceTopbar({
  assistantVisible,
  dataOrigin = "mock",
  onOpenNavigation,
  onToggleAssistant,
  onOpenHelp,
  onResetWorkspace,
}: {
  assistantVisible: boolean;
  dataOrigin?: DataOrigin;
  onOpenNavigation: () => void;
  onToggleAssistant: () => void;
  onOpenHelp: () => void;
  onResetWorkspace?: () => void;
}) {
  const originDisplay = getDataOriginDisplay(dataOrigin);

  return (
    <header className="workspace-topbar">
      <button
        className="icon-button workspace-mobile-menu"
        type="button"
        aria-label="Open workspace navigation"
        onClick={onOpenNavigation}
      >
        <Icon name="menu" />
      </button>
      <BrandMark href="/" />
      <div className="topbar-workspace-name">
        <span className="topbar-separator" aria-hidden="true" />
        <p>
          <small>Workspace</small>Analysis Workspace
        </p>
        <span
          className="topbar-data-origin"
          role="status"
          title={originDisplay.description}
          aria-label={`Data Origin: ${originDisplay.label}`}
        >
          {originDisplay.label}
        </span>
      </div>
      <div className="topbar-actions">
        <ServiceStatus compact />
        {onResetWorkspace ? (
          <button
            className="icon-button"
            type="button"
            aria-label="Reset workspace"
            title="Reset workspace"
            onClick={onResetWorkspace}
          >
            <Icon name="history" />
          </button>
        ) : null}
        <button
          className="icon-button"
          type="button"
          aria-label="Open workspace guide"
          onClick={onOpenHelp}
        >
          <Icon name="help" />
        </button>
        <button
          className={`panel-toggle ${assistantVisible ? "active" : ""}`}
          type="button"
          aria-pressed={assistantVisible}
          aria-controls="assistant-region"
          onClick={onToggleAssistant}
        >
          <Icon name="panel" />
          <span>{assistantVisible ? "Hide assistant" : "Show assistant"}</span>
        </button>
        <Link className="icon-button topbar-home" href="/" aria-label="Return to homepage">
          <Icon name="home" />
        </Link>
      </div>
    </header>
  );
}
