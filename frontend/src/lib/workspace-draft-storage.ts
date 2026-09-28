import { z } from "zod";
import { type AnalysisMode, analysisModeSchema } from "./analysis-contracts";
import { AOI_MAX_FILE_BYTES, createSelectedAoi, type SelectedAoi } from "./aoi";
import { type PairingPreferences, pairingPreferencesSchema } from "./temporal-contracts";

export const WORKSPACE_DRAFT_STORAGE_KEY = "satquery.workspace.draft.v1";
export const WORKSPACE_DRAFT_SCHEMA_VERSION = 1 as const;
export const WORKSPACE_DRAFT_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

const resultTabSchema = z.enum(["answer", "evidence", "activity"]);
export type ResultTab = z.infer<typeof resultTabSchema>;

export const sceneFiltersDraftSchema = z.object({
  maxCloudCover: z.number().min(0).max(100).default(20),
  sensorType: z.enum(["optical", "sar", "multispectral", "unknown"]).default("optical"),
  limit: z.number().min(1).max(100).default(12),
});
export type SceneFiltersDraft = z.infer<typeof sceneFiltersDraftSchema>;

export const workspaceDraftSchema = z.object({
  version: z.literal(1),
  savedAt: z.string(),
  updatedAt: z.string(),
  analysisMode: analysisModeSchema.default("visual_question_answering"),
  questionDraft: z.string().max(1000).default(""),
  aoi: z
    .object({
      feature: z.record(z.string(), z.unknown()),
      source: z.enum(["rectangle", "polygon", "bbox", "geojson"]),
    })
    .nullable()
    .optional(),
  dateRange: z
    .object({
      start_date: z.string(),
      end_date: z.string(),
    })
    .nullable()
    .optional(),
  beforeWindow: z
    .object({
      start_date: z.string(),
      end_date: z.string(),
      label: z.string().default("before"),
      target_date: z.string().nullable().optional(),
    })
    .nullable()
    .optional(),
  afterWindow: z
    .object({
      start_date: z.string(),
      end_date: z.string(),
      label: z.string().default("after"),
      target_date: z.string().nullable().optional(),
    })
    .nullable()
    .optional(),
  selectedBeforeSceneId: z.string().nullable().optional(),
  selectedAfterSceneId: z.string().nullable().optional(),
  pairingPreferences: pairingPreferencesSchema.nullable().optional(),
  sceneFilters: sceneFiltersDraftSchema.default({
    maxCloudCover: 20,
    sensorType: "optical",
    limit: 12,
  }),
  activeTab: resultTabSchema.default("answer"),
  mapCamera: z
    .object({
      center: z.tuple([z.number(), z.number()]),
      zoom: z.number(),
    })
    .nullable()
    .optional(),
});

export type WorkspaceDraftPayload = z.infer<typeof workspaceDraftSchema>;

export interface RestoredWorkspaceDraft {
  readonly analysisMode: AnalysisMode;
  readonly questionDraft: string;
  readonly aoi: SelectedAoi | null;
  readonly dateRange: { start_date: string; end_date: string } | null;
  readonly beforeWindow: { start_date: string; end_date: string; label?: string } | null;
  readonly afterWindow: { start_date: string; end_date: string; label?: string } | null;
  readonly selectedBeforeSceneId: string | null;
  readonly selectedAfterSceneId: string | null;
  readonly pairingPreferences: PairingPreferences | null;
  readonly sceneFilters: SceneFiltersDraft;
  readonly activeTab: ResultTab;
  readonly mapCamera: { center: [number, number]; zoom: number } | null;
  readonly savedAt: string;
  readonly updatedAt: string;
}

export function isDraftExpired(savedAt: string, ttlMs: number = WORKSPACE_DRAFT_TTL_MS): boolean {
  const timestamp = Date.parse(savedAt);
  if (!Number.isFinite(timestamp)) return true;
  return Date.now() - timestamp > ttlMs;
}

export function serializeWorkspaceDraft(
  state: {
    analysisMode: AnalysisMode;
    questionDraft: string;
    aoi: SelectedAoi | null;
    dateRange: { start_date: string; end_date: string } | null;
    beforeWindow?: { start_date: string; end_date: string; label?: string } | null;
    afterWindow?: { start_date: string; end_date: string; label?: string } | null;
    selectedBeforeSceneId?: string | null;
    selectedAfterSceneId?: string | null;
    pairingPreferences?: PairingPreferences | null;
    sceneFilters?: SceneFiltersDraft;
    activeTab?: ResultTab;
    mapCamera?: { center: [number, number]; zoom: number } | null;
  },
  savedAt = new Date().toISOString(),
): string {
  const payload: WorkspaceDraftPayload = {
    version: 1,
    savedAt,
    updatedAt: new Date().toISOString(),
    analysisMode: state.analysisMode,
    questionDraft: state.questionDraft.slice(0, 1000),
    aoi: state.aoi
      ? {
          feature: state.aoi.feature as unknown as Record<string, unknown>,
          source: state.aoi.source,
        }
      : null,
    dateRange: state.dateRange,
    beforeWindow: state.beforeWindow
      ? {
          start_date: state.beforeWindow.start_date,
          end_date: state.beforeWindow.end_date,
          label: state.beforeWindow.label ?? "before",
        }
      : null,
    afterWindow: state.afterWindow
      ? {
          start_date: state.afterWindow.start_date,
          end_date: state.afterWindow.end_date,
          label: state.afterWindow.label ?? "after",
        }
      : null,
    selectedBeforeSceneId: state.selectedBeforeSceneId ?? null,
    selectedAfterSceneId: state.selectedAfterSceneId ?? null,
    pairingPreferences: state.pairingPreferences ?? null,
    sceneFilters: state.sceneFilters ?? {
      maxCloudCover: 20,
      sensorType: "optical",
      limit: 12,
    },
    activeTab: state.activeTab ?? "answer",
    mapCamera: state.mapCamera ?? null,
  };
  return JSON.stringify(payload);
}

export function parseWorkspaceDraft(rawJson: string): RestoredWorkspaceDraft {
  if (rawJson.length > AOI_MAX_FILE_BYTES) {
    throw new Error("Stored workspace draft exceeds maximum allowed size.");
  }

  let parsedJson: unknown;
  try {
    parsedJson = JSON.parse(rawJson);
  } catch {
    throw new Error("Stored workspace draft is corrupted JSON.");
  }

  const result = workspaceDraftSchema.safeParse(parsedJson);
  if (!result.success) {
    throw new Error("Stored workspace draft schema is invalid or unsupported.");
  }

  const data = result.data;
  if (isDraftExpired(data.savedAt)) {
    throw new Error("Stored workspace draft has expired (> 7 days old).");
  }

  let restoredAoi: SelectedAoi | null = null;
  if (data.aoi?.feature && data.aoi.source) {
    try {
      restoredAoi = createSelectedAoi(data.aoi.feature, data.aoi.source);
    } catch {
      // If AOI feature fails creation, degrade gracefully without throwing
      restoredAoi = null;
    }
  }

  return {
    analysisMode: data.analysisMode,
    questionDraft: data.questionDraft,
    aoi: restoredAoi,
    dateRange: data.dateRange ?? null,
    beforeWindow: data.beforeWindow ?? null,
    afterWindow: data.afterWindow ?? null,
    selectedBeforeSceneId: data.selectedBeforeSceneId ?? null,
    selectedAfterSceneId: data.selectedAfterSceneId ?? null,
    pairingPreferences: data.pairingPreferences ?? null,
    sceneFilters: data.sceneFilters,
    activeTab: data.activeTab,
    mapCamera: data.mapCamera ?? null,
    savedAt: data.savedAt,
    updatedAt: data.updatedAt,
  };
}

export function saveWorkspaceDraftToStorage(
  rawSerialized: string,
  storageKey: string = WORKSPACE_DRAFT_STORAGE_KEY,
): { success: boolean; error?: string } {
  try {
    if (typeof window === "undefined" || !window.localStorage) {
      return { success: false, error: "localStorage is unavailable." };
    }
    window.localStorage.setItem(storageKey, rawSerialized);
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to write to localStorage.",
    };
  }
}

export function clearWorkspaceDraftFromStorage(
  storageKey: string = WORKSPACE_DRAFT_STORAGE_KEY,
): void {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.removeItem(storageKey);
    }
  } catch {
    // Ignore storage clear errors safely
  }
}
