"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { CatalogueClientError, type CatalogueScene, getCatalogueItem } from "@/lib/catalog-client";
import {
  catalogueSceneIdentity,
  createCatalogueSceneSelection,
  type SelectedCatalogueScene,
} from "@/lib/scene-selection";
import {
  parseStoredSceneSelection,
  SCENE_SELECTION_STORAGE_KEY,
  serializeStoredSceneSelection,
} from "@/lib/scene-selection-storage";

export type SceneSelectionPersistenceState =
  | "loading"
  | "empty"
  | "saved"
  | "restored"
  | "refreshing"
  | "stale"
  | "unavailable";

export interface SceneSelectionDraftClient {
  getItem: typeof getCatalogueItem;
}

const defaultClient: SceneSelectionDraftClient = { getItem: getCatalogueItem };

function identitiesMatch(selection: SelectedCatalogueScene, scene: CatalogueScene) {
  const identity = catalogueSceneIdentity(scene);
  return (
    identity.providerId === selection.identity.providerId &&
    identity.collectionId === selection.identity.collectionId &&
    identity.itemId === selection.identity.itemId
  );
}

export function useSceneSelectionDraft(client: SceneSelectionDraftClient = defaultClient) {
  const [selectedScene, setSelectedScene] = useState<SelectedCatalogueScene | null>(null);
  const [persistenceState, setPersistenceState] =
    useState<SceneSelectionPersistenceState>("loading");
  const [persistenceMessage, setPersistenceMessage] = useState<string | null>(null);
  const refreshController = useRef<AbortController | null>(null);

  const refreshCandidate = useCallback(
    async (selection: SelectedCatalogueScene, restoring: boolean) => {
      refreshController.current?.abort();
      const controller = new AbortController();
      refreshController.current = controller;
      setPersistenceState("refreshing");
      setPersistenceMessage(
        restoring
          ? "Restored from this browser. Refreshing catalogue metadata..."
          : "Refreshing catalogue metadata...",
      );
      try {
        const scene = await client.getItem(
          selection.identity.providerId,
          selection.identity.collectionId,
          selection.identity.itemId,
          controller.signal,
        );
        if (!identitiesMatch(selection, scene)) {
          throw new CatalogueClientError(
            "unexpected_response",
            "SatQuery returned metadata for a different catalogue scene.",
          );
        }
        const refreshed = createCatalogueSceneSelection(
          scene,
          selection.queryFingerprint,
          selection.query,
        );
        setSelectedScene(refreshed);
        try {
          window.localStorage.setItem(
            SCENE_SELECTION_STORAGE_KEY,
            serializeStoredSceneSelection(refreshed),
          );
          setPersistenceState(restoring ? "restored" : "saved");
          setPersistenceMessage(
            restoring
              ? "Restored with current metadata. Saved in this browser."
              : "Metadata refreshed. Saved in this browser.",
          );
        } catch {
          setPersistenceState("unavailable");
          setPersistenceMessage(
            "Current metadata was loaded, but browser storage could not be updated.",
          );
        }
      } catch (error) {
        if (error instanceof CatalogueClientError && error.kind === "cancelled") return;
        setPersistenceState("stale");
        setPersistenceMessage(
          error instanceof CatalogueClientError && error.kind === "not_found"
            ? "This saved scene is no longer available from the catalogue. Preserved metadata may be stale."
            : "Current catalogue metadata is unavailable. Preserved metadata may be stale.",
        );
      } finally {
        if (refreshController.current === controller) refreshController.current = null;
      }
    },
    [client],
  );

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(SCENE_SELECTION_STORAGE_KEY);
      if (!stored) {
        setPersistenceState("empty");
        return;
      }
      try {
        const restored = parseStoredSceneSelection(stored).selection;
        setSelectedScene(restored);
        void refreshCandidate(restored, true);
      } catch (error) {
        window.localStorage.removeItem(SCENE_SELECTION_STORAGE_KEY);
        setPersistenceState("unavailable");
        setPersistenceMessage(
          error instanceof Error
            ? error.message
            : "The saved scene selection could not be restored.",
        );
      }
    } catch {
      setPersistenceState("unavailable");
      setPersistenceMessage(
        "Browser storage is unavailable. Scene selection remains usable in this tab.",
      );
    }
    return () => refreshController.current?.abort();
  }, [refreshCandidate]);

  const selectScene = useCallback((selection: SelectedCatalogueScene) => {
    refreshController.current?.abort();
    setSelectedScene(selection);
    try {
      window.localStorage.setItem(
        SCENE_SELECTION_STORAGE_KEY,
        serializeStoredSceneSelection(selection),
      );
      setPersistenceState("saved");
      setPersistenceMessage("Saved in this browser. Metadata selection only.");
    } catch {
      setPersistenceState("unavailable");
      setPersistenceMessage(
        "The scene selection could not be saved. It remains usable in this tab.",
      );
    }
  }, []);

  const clearScene = useCallback((message?: string) => {
    refreshController.current?.abort();
    setSelectedScene(null);
    try {
      window.localStorage.removeItem(SCENE_SELECTION_STORAGE_KEY);
      setPersistenceState("empty");
      setPersistenceMessage(message ?? "No scene selection is saved in this browser.");
    } catch {
      setPersistenceState("unavailable");
      setPersistenceMessage(
        message ?? "Browser storage could not be cleared; the current tab is clear.",
      );
    }
  }, []);

  const refreshScene = useCallback(() => {
    if (selectedScene) void refreshCandidate(selectedScene, false);
  }, [refreshCandidate, selectedScene]);

  return {
    selectedScene,
    selectScene,
    clearScene,
    refreshScene,
    persistenceState,
    persistenceMessage,
  };
}
