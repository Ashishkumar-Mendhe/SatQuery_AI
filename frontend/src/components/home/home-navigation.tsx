"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { Icon } from "@/components/icon";

const sectionLinks = [
  { href: "#workflow", label: "Workflow" },
  { href: "#capabilities", label: "Capabilities" },
  { href: "#evidence", label: "Evidence" },
];

export function HomeNavigation() {
  const [menuOpen, setMenuOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  return (
    <header className="home-header">
      <nav className="home-nav page-width" aria-label="Primary navigation">
        <BrandMark />
        <div className="desktop-nav-links">
          {sectionLinks.map((link) => (
            <a href={link.href} key={link.href}>
              {link.label}
            </a>
          ))}
        </div>
        <Link className="button button-primary desktop-workspace-link" href="/workspace">
          Open workspace
          <Icon className="button-icon" name="arrow" />
        </Link>
        <button
          ref={toggleRef}
          className="icon-button mobile-menu-toggle"
          type="button"
          aria-expanded={menuOpen}
          aria-controls="home-mobile-menu"
          aria-label={menuOpen ? "Close navigation" : "Open navigation"}
          onClick={() => setMenuOpen((current) => !current)}
        >
          <Icon name={menuOpen ? "close" : "menu"} />
        </button>
      </nav>
      <div
        className={`mobile-menu ${menuOpen ? "is-open" : ""}`}
        id="home-mobile-menu"
        hidden={!menuOpen}
      >
        <nav aria-label="Mobile navigation">
          {sectionLinks.map((link) => (
            <a href={link.href} key={link.href} onClick={() => setMenuOpen(false)}>
              {link.label}
            </a>
          ))}
          <Link className="button button-primary" href="/workspace">
            Open workspace
            <Icon className="button-icon" name="arrow" />
          </Link>
        </nav>
      </div>
    </header>
  );
}
