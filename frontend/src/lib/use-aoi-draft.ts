"use client";

import { useCallback, useEffect, useState } from "react";

import type { SelectedAoi } from "@/lib/aoi";
import { AOI_STORAGE_KEY, parseStoredAoi, serializeStoredAoi } from "@/lib/aoi-storage";

export type AoiPersistenceState = "loading" | "empty" | "saved" | "restored" | "unavailable";

export function useAoiDraft() {
  const [aoi, setAoiState] = useState<SelectedAoi | null>(null);
  const [persistenceState, setPersistenceState] = useState<AoiPersistenceState>("loading");
  const [persistenceMessage, setPersistenceMessage] = useState(
    "Checking this browser for an AOI draft…",
  );

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(AOI_STORAGE_KEY);
      if (!stored) {
        setPersistenceState("empty");
        setPersistenceMessage("No AOI is saved in this browser.");
        return;
      }
      try {
        setAoiState(parseStoredAoi(stored));
        setPersistenceState("restored");
        setPersistenceMessage("Restored from this browser.");
      } catch (error) {
        window.localStorage.removeItem(AOI_STORAGE_KEY);
        setPersistenceState("unavailable");
        setPersistenceMessage(
          error instanceof Error ? error.message : "The saved AOI draft could not be restored.",
        );
      }
    } catch {
      setPersistenceState("unavailable");
      setPersistenceMessage("Browser storage is unavailable. The AOI remains usable in this tab.");
    }
  }, []);

  const setAoi = useCallback((nextAoi: SelectedAoi) => {
    setAoiState(nextAoi);
    try {
      window.localStorage.setItem(AOI_STORAGE_KEY, serializeStoredAoi(nextAoi));
      setPersistenceState("saved");
      setPersistenceMessage("Saved in this browser.");
    } catch {
      setPersistenceState("unavailable");
      setPersistenceMessage(
        "The AOI could not be saved. It remains usable in this tab; refresh may restore an older draft.",
      );
    }
  }, []);

  const clearAoi = useCallback(() => {
    setAoiState(null);
    try {
      window.localStorage.removeItem(AOI_STORAGE_KEY);
      setPersistenceState("empty");
      setPersistenceMessage("No AOI is saved in this browser.");
    } catch {
      setPersistenceState("unavailable");
      setPersistenceMessage("Browser storage could not be cleared; the current tab is clear.");
    }
  }, []);

  return { aoi, setAoi, clearAoi, persistenceState, persistenceMessage };
}
