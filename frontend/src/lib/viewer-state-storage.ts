import { type SavedViewerState, savedViewerStateSchema } from "@/lib/viewer-contracts";

export const VIEWER_STATE_STORAGE_KEY = "satquery.viewer-state.v1";
export const VIEWER_STATE_MAX_BYTES = 256_000;

export function serializeViewerState(state: SavedViewerState): string {
  const parsed = savedViewerStateSchema.parse(state);
  const serialized = JSON.stringify(parsed);
  if (serialized.length > VIEWER_STATE_MAX_BYTES)
    throw new Error("Viewer state exceeds the storage limit.");
  return serialized;
}

export function parseViewerState(value: string): SavedViewerState {
  if (value.length > VIEWER_STATE_MAX_BYTES)
    throw new Error("Saved viewer state exceeds the storage limit.");
  let decoded: unknown;
  try {
    decoded = JSON.parse(value);
  } catch {
    throw new Error("Saved viewer state is corrupt.");
  }
  const parsed = savedViewerStateSchema.safeParse(decoded);
  if (!parsed.success) throw new Error("Saved viewer state is invalid or unsupported.");
  return parsed.data;
}
