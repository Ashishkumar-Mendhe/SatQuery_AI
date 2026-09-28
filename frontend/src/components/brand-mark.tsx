import type { Route } from "next";
import Link from "next/link";

export function BrandMark({ href = "/", compact = false }: { href?: Route; compact?: boolean }) {
  return (
    <Link className="brand-mark" href={href} aria-label="SatQuery home">
      <svg aria-hidden="true" className="brand-symbol" viewBox="0 0 36 36">
        <circle cx="18" cy="18" r="8.75" />
        <path d="M6.2 20.6c4.9 4.4 13.2 6.5 20.4 3.4 3.8-1.7 5.3-4 4.7-5.7-.9-2.4-6.5-2.7-12.6-.8C12 19.7 7.9 23.8 9.4 26.2c1.2 1.9 5.4 2 10.2.5" />
        <circle className="brand-satellite" cx="29.4" cy="16.8" r="1.8" />
      </svg>
      <span className={compact ? "sr-only" : undefined}>SatQuery</span>
    </Link>
  );
}
