import { AOI_MAX_FILE_BYTES, createSelectedAoi, type SelectedAoi } from "@/lib/aoi";

export const AOI_STORAGE_KEY = "satquery.aoi-draft.v1";

export interface StoredAoiDraft {
  version: 1;
  savedAt: string;
  aoi: SelectedAoi;
}

export function serializeStoredAoi(aoi: SelectedAoi, savedAt = new Date()): string {
  const payload: StoredAoiDraft = {
    version: 1,
    savedAt: savedAt.toISOString(),
    aoi,
  };
  return JSON.stringify(payload);
}

export function parseStoredAoi(value: string): SelectedAoi {
  if (value.length > AOI_MAX_FILE_BYTES)
    throw new Error("The saved AOI draft exceeds the size limit.");
  let payload: unknown;
  try {
    payload = JSON.parse(value);
  } catch {
    throw new Error("The saved AOI draft is corrupt and could not be restored.");
  }
  if (
    typeof payload !== "object" ||
    payload === null ||
    !("version" in payload) ||
    payload.version !== 1 ||
    !("aoi" in payload) ||
    typeof payload.aoi !== "object" ||
    payload.aoi === null
  ) {
    throw new Error("The saved AOI draft uses an unsupported format.");
  }
  const stored = payload.aoi as Record<string, unknown>;
  if (!("feature" in stored) || !("source" in stored)) {
    throw new Error("The saved AOI draft is incomplete.");
  }
  const source = stored.source;
  if (!(["rectangle", "polygon", "bbox", "geojson"] as unknown[]).includes(source)) {
    throw new Error("The saved AOI draft has an unsupported source.");
  }
  return createSelectedAoi(stored.feature, source as SelectedAoi["source"]);
}
