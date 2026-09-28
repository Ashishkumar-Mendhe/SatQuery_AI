import type { SVGProps } from "react";

export type IconName =
  | "activity"
  | "arrow"
  | "check"
  | "chevron"
  | "close"
  | "evidence"
  | "help"
  | "history"
  | "home"
  | "layers"
  | "location"
  | "map"
  | "menu"
  | "mission"
  | "panel"
  | "question"
  | "report"
  | "spark"
  | "target"
  | "warning";

export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.7,
  };

  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" {...props}>
      <g {...common}>
        {name === "activity" ? <path d="M4 17V7m5 10v-5m5 5V4m5 13V9" /> : null}
        {name === "arrow" ? <path d="m5 12 14 0m-5-5 5 5-5 5" /> : null}
        {name === "check" ? <path d="m5 13 4 4L19 7" /> : null}
        {name === "chevron" ? <path d="m9 6 6 6-6 6" /> : null}
        {name === "close" ? <path d="m6 6 12 12M18 6 6 18" /> : null}
        {name === "evidence" ? (
          <>
            <path d="M5 4h14v16H5z" />
            <path d="m8 14 2.5-2.5 2 2L16 10l1.5 1.5M8 7h5" />
          </>
        ) : null}
        {name === "help" ? (
          <>
            <circle cx="12" cy="12" r="9" />
            <path d="M9.7 9a2.4 2.4 0 1 1 3.2 2.3c-.8.35-.9.95-.9 1.7M12 17h.01" />
          </>
        ) : null}
        {name === "history" ? (
          <>
            <path d="M4 11a8 8 0 1 1 2.3 6.2M4 5v6h6" />
            <path d="M12 8v4l3 2" />
          </>
        ) : null}
        {name === "home" ? (
          <>
            <path d="m3 11 9-7 9 7" />
            <path d="M5.5 9.5V20h13V9.5M9.5 20v-6h5v6" />
          </>
        ) : null}
        {name === "layers" ? (
          <>
            <path d="m12 3 9 5-9 5-9-5 9-5Z" />
            <path d="m3 12 9 5 9-5M3 16l9 5 9-5" />
          </>
        ) : null}
        {name === "location" ? (
          <>
            <path d="M12 21s-7-5.5-7-11a7 7 0 1 1 14 0c0 5.5-7 11-7 11Z" />
            <circle cx="12" cy="10" r="2.5" />
          </>
        ) : null}
        {name === "map" ? (
          <>
            <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z" />
            <path d="M9 3v15m6-12v15" />
          </>
        ) : null}
        {name === "menu" ? <path d="M4 7h16M4 12h16M4 17h16" /> : null}
        {name === "mission" ? (
          <>
            <circle cx="12" cy="12" r="3" />
            <circle cx="12" cy="12" r="8" />
            <path d="M12 2v3m0 14v3M2 12h3m14 0h3" />
          </>
        ) : null}
        {name === "panel" ? (
          <>
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <path d="M15 4v16" />
          </>
        ) : null}
        {name === "question" ? (
          <>
            <path d="M5 4h14v13H9l-4 3V4Z" />
            <path d="M8 8h8m-8 4h5" />
          </>
        ) : null}
        {name === "report" ? (
          <>
            <path d="M6 3h9l3 3v15H6V3Z" />
            <path d="M14 3v4h4M9 12h6m-6 4h6" />
          </>
        ) : null}
        {name === "spark" ? (
          <path d="m12 2 1.6 5.2L19 9l-5.4 1.8L12 16l-1.6-5.2L5 9l5.4-1.8L12 2Zm6 13 .8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8L18 15Z" />
        ) : null}
        {name === "target" ? (
          <>
            <circle cx="12" cy="12" r="8" />
            <circle cx="12" cy="12" r="3" />
            <path d="M12 2v3m0 14v3M2 12h3m14 0h3" />
          </>
        ) : null}
        {name === "warning" ? (
          <>
            <path d="m12 3 9 16H3L12 3Z" />
            <path d="M12 9v4m0 3h.01" />
          </>
        ) : null}
      </g>
    </svg>
  );
}
