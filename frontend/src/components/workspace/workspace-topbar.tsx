"use client";

import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";
import { Icon } from "@/components/icon";
import { ServiceStatus } from "@/components/service-status";

export function WorkspaceTopbar({
  assistantVisible,
  onOpenNavigation,
  onToggleAssistant,
  onOpenHelp,
}: {
  assistantVisible: boolean;
  onOpenNavigation: () => void;
  onToggleAssistant: () => void;
  onOpenHelp: () => void;
}) {
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
          <small>Workspace</small>Untitled workspace
        </p>
      </div>
      <div className="topbar-actions">
        <ServiceStatus compact />
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
