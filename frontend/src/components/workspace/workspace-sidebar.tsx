"use client";

import Link from "next/link";
import { useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { Icon, type IconName } from "@/components/icon";
import { featureAvailability } from "@/lib/feature-availability";

const futureDestinations: Array<{
  label: string;
  icon: IconName;
  explanation: string;
}> = [
  { label: "History", icon: "history", explanation: featureAvailability.history.explanation },
  { label: "Saved AOIs", icon: "target", explanation: featureAvailability.savedAois.explanation },
  { label: "Missions", icon: "mission", explanation: featureAvailability.missions.explanation },
  { label: "Reports", icon: "report", explanation: featureAvailability.reports.explanation },
];

export function WorkspaceSidebar({
  collapsed,
  mobileOpen,
  onToggleCollapse,
  onCloseMobile,
}: {
  collapsed: boolean;
  mobileOpen: boolean;
  onToggleCollapse: () => void;
  onCloseMobile: () => void;
}) {
  const [availabilityMessage, setAvailabilityMessage] = useState(
    "Planned sections explain their availability here; they do not open incomplete routes.",
  );

  return (
    <aside
      className={`workspace-sidebar ${mobileOpen ? "mobile-open" : ""}`}
      aria-label="Workspace navigation"
    >
      <div className="sidebar-mobile-header">
        <BrandMark />
        <button
          className="icon-button"
          type="button"
          aria-label="Close navigation"
          onClick={onCloseMobile}
        >
          <Icon name="close" />
        </button>
      </div>
      <nav className="workspace-nav" aria-label="Workspace sections">
        <Link className="workspace-nav-item active" href="/workspace" aria-current="page">
          <Icon name="map" />
          <span className="nav-label">Workspace</span>
        </Link>
        <div className="workspace-nav-divider" />
        {futureDestinations.map((item) => (
          <button
            className="workspace-nav-item planned"
            key={item.label}
            type="button"
            aria-describedby="sidebar-availability"
            onClick={() => setAvailabilityMessage(`${item.label}: ${item.explanation}`)}
          >
            <Icon name={item.icon} />
            <span className="nav-label">{item.label}</span>
            <span className="nav-planned">Planned</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-availability" id="sidebar-availability" aria-live="polite">
        <Icon name="help" />
        <p>{availabilityMessage}</p>
      </div>
      <div className="sidebar-footer">
        <Link className="workspace-nav-item" href="/">
          <Icon name="home" />
          <span className="nav-label">Return home</span>
        </Link>
        <button
          className="workspace-nav-item sidebar-collapse-button"
          type="button"
          aria-label={collapsed ? "Expand navigation sidebar" : "Collapse navigation sidebar"}
          aria-expanded={!collapsed}
          onClick={onToggleCollapse}
        >
          <Icon className={collapsed ? "rotate-180" : undefined} name="chevron" />
          <span className="nav-label">Collapse sidebar</span>
        </button>
      </div>
    </aside>
  );
}
