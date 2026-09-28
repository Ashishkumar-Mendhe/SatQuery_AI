"use client";

import { AccessibleDialog } from "./accessible-dialog";

export interface ResetWorkspaceDialogProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onConfirm: () => void;
}

export function ResetWorkspaceDialog({ open, onClose, onConfirm }: ResetWorkspaceDialogProps) {
  function handleConfirm() {
    onConfirm();
    onClose();
  }

  return (
    <AccessibleDialog
      open={open}
      onClose={onClose}
      title="Reset Workspace?"
      description="This will clear your active AOI, question draft, temporal parameters, and stored browser draft. This action cannot be undone."
    >
      <div className="reset-dialog-actions">
        <button type="button" className="button button-quiet" onClick={onClose}>
          Cancel
        </button>
        <button type="button" className="button button-primary danger" onClick={handleConfirm}>
          Reset Workspace
        </button>
      </div>
    </AccessibleDialog>
  );
}
