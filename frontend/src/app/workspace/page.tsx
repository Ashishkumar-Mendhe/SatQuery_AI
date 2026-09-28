import type { Metadata } from "next";

import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export const metadata: Metadata = {
  title: "Workspace",
  description: "The unified SatQuery Earth-observation workspace.",
};

export default function WorkspacePage() {
  return <WorkspaceShell />;
}
