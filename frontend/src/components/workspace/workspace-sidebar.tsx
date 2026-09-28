"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import type { Route } from "next";
import { BrandMark } from "@/components/brand-mark";
import { Icon, type IconName } from "@/components/icon";

const activeNavItems: Array<{
  label: string;
  href: Route;
  icon: IconName;
}> = [
  { label: "Workspace", href: "/workspace", icon: "map" },
  { label: "History", href: "/history", icon: "history" },
  { label: "Saved AOIs", href: "/saved-aois", icon: "target" },
  { label: "Reports", href: "/reports", icon: "report" },
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
  const pathname = usePathname();
  const [availabilityMessage, setAvailabilityMessage] = useState(
    "Active sections link to operational workspace features; future roadmap items are clearly marked.",
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
        {activeNavItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              className={`workspace-nav-item ${isActive ? "active" : ""}`}
              href={item.href}
              title={collapsed ? item.label : undefined}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon name={item.icon} />
              <span className="nav-label">{item.label}</span>
            </Link>
          );
        })}
        <div className="workspace-nav-divider" />
        <button
          className="workspace-nav-item planned"
          type="button"
          title={collapsed ? "Missions (Planned Phase 12)" : undefined}
          aria-describedby="sidebar-availability"
          onClick={() =>
            setAvailabilityMessage(
              "Missions: Multi-target persistent campaign monitoring is scheduled for Roadmap Phase 12.",
            )
          }
        >
          <Icon name="mission" />
          <span className="nav-label">Missions</span>
          <span className="nav-planned" title="Roadmap Phase 12 scope">
            Phase 12
          </span>
        </button>
      </nav>
      <div className="sidebar-availability" id="sidebar-availability" aria-live="polite">
        <Icon name="help" />
        <p>{availabilityMessage}</p>
      </div>
      <div className="sidebar-footer">
        <Link className="workspace-nav-item" href="/" title={collapsed ? "Return home" : undefined}>
          <Icon name="home" />
          <span className="nav-label">Return home</span>
        </Link>
        <button
          className="workspace-nav-item sidebar-collapse-button"
          type="button"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
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
