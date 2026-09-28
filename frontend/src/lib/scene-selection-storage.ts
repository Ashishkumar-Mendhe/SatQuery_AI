import { z } from "zod";

import {
  type CatalogueScene,
  catalogueSceneSchema,
  catalogueSearchRequestSchema,
} from "@/lib/catalog-client";
import {
  type CatalogueSceneIdentity,
  catalogueQueryFingerprintFromRequest,
  catalogueSceneIdentity,
  catalogueSceneKey,
  type SelectedCatalogueScene,
  type StoredPreviewMetadata,
} from "@/lib/scene-selection";

export const SCENE_SELECTION_STORAGE_KEY = "satquery.scene-selection-draft.v1";
export const SCENE_SELECTION_MAX_BYTES = 256_000;

const utcTimestampSchema = z
  .string()
  .refine(
    (value) => /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value)),
    "Expected an ISO 8601 timestamp with a timezone offset.",
  );
const identitySchema = z
  .object({
    providerId: z.string().min(1).max(64),
    collectionId: z.string().min(1).max(512),
    itemId: z.string().min(1).max(512),
  })
  .strict();
const previewMetadataSchema = z
  .object({
    purpose: z.enum(["thumbnail", "preview"]),
    access: z.enum(["public", "temporary", "backend_mediated", "unavailable"]),
    media_type: z.string().min(1).max(160).nullable(),
    width: z.number().int().positive().max(20_000).nullable(),
    height: z.number().int().positive().max(20_000).nullable(),
    attribution: z.string().min(1).max(500).nullable(),
  })
  .strict();
const storedSelectionSchema = z
  .object({
    version: z.literal(1),
    savedAt: utcTimestampSchema,
    identity: identitySchema,
    queryFingerprint: z.string().min(1).max(200_000),
    query: catalogueSearchRequestSchema,
    scene: catalogueSceneSchema,
    previewMetadata: previewMetadataSchema.nullable(),
  })
  .strict();

export interface StoredSceneSelectionDraft {
  version: 1;
  savedAt: string;
  identity: CatalogueSceneIdentity;
  queryFingerprint: string;
  query: SelectedCatalogueScene["query"];
  scene: CatalogueScene;
  previewMetadata: StoredPreviewMetadata | null;
}

function sameIdentity(left: CatalogueSceneIdentity, right: CatalogueSceneIdentity) {
  return (
    left.providerId === right.providerId &&
    left.collectionId === right.collectionId &&
    left.itemId === right.itemId
  );
}

function geometryRings(geometry: CatalogueScene["footprint"]) {
  return geometry.type === "Polygon" ? geometry.coordinates : geometry.coordinates.flat();
}

function validateGeometry(scene: CatalogueScene) {
  const rings = geometryRings(scene.footprint);
  const positions = rings.flat();
  if (positions.length > 500) throw new Error("The saved scene footprint is too complex.");
  for (const ring of rings) {
    const first = ring[0];
    const last = ring[ring.length - 1];
    if (!first || !last || first[0] !== last[0] || first[1] !== last[1]) {
      throw new Error("The saved scene footprint contains an open ring.");
    }
  }
  for (const [longitude, latitude] of positions) {
    if (longitude < -180 || longitude > 180 || latitude < -90 || latitude > 90) {
      throw new Error("The saved scene footprint contains an invalid coordinate.");
    }
  }
  const longitudes = positions.map(([longitude]) => longitude);
  const latitudes = positions.map(([, latitude]) => latitude);
  const derived = [
    Math.min(...longitudes),
    Math.min(...latitudes),
    Math.max(...longitudes),
    Math.max(...latitudes),
  ];
  if (derived.some((value, index) => Math.abs(value - scene.bbox[index]) > 1e-9)) {
    throw new Error("The saved scene footprint and bounds do not match.");
  }
}

function validateDurableReferences(scene: CatalogueScene) {
  if (!scene.license?.url) return;
  const licenseUrl = new URL(scene.license.url);
  if (
    licenseUrl.protocol !== "https:" ||
    licenseUrl.username.length > 0 ||
    licenseUrl.password.length > 0
  ) {
    throw new Error("The saved scene contains an unsafe licence reference.");
  }
}

export function serializeStoredSceneSelection(
  selection: SelectedCatalogueScene,
  savedAt = new Date(),
): string {
  if (selection.queryFingerprint !== catalogueQueryFingerprintFromRequest(selection.query)) {
    throw new Error("The scene selection query fingerprint does not match its query.");
  }
  const payload: StoredSceneSelectionDraft = {
    version: 1,
    savedAt: savedAt.toISOString(),
    identity: selection.identity,
    queryFingerprint: selection.queryFingerprint,
    query: { ...selection.query, cursor: null },
    scene: { ...selection.scene, preview: null },
    previewMetadata: selection.previewMetadata,
  };
  const serialized = JSON.stringify(payload);
  if (serialized.length > SCENE_SELECTION_MAX_BYTES) {
    throw new Error("The scene selection draft exceeds the browser storage size limit.");
  }
  return serialized;
}

export function parseStoredSceneSelection(value: string): {
  selection: SelectedCatalogueScene;
  savedAt: string;
} {
  if (value.length > SCENE_SELECTION_MAX_BYTES) {
    throw new Error("The saved scene selection exceeds the size limit.");
  }
  let raw: unknown;
  try {
    raw = JSON.parse(value);
  } catch {
    throw new Error("The saved scene selection is corrupt and could not be restored.");
  }
  if (typeof raw !== "object" || raw === null || !("version" in raw) || raw.version !== 1) {
    throw new Error("The saved scene selection uses an unsupported format.");
  }
  const parsed = storedSelectionSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error("The saved scene selection is invalid and could not be restored.");
  }
  const draft = parsed.data;
  const sceneIdentity = catalogueSceneIdentity(draft.scene);
  if (!sameIdentity(draft.identity, sceneIdentity)) {
    throw new Error("The saved scene identity does not match its metadata.");
  }
  if (
    draft.query.cursor !== null ||
    draft.query.provider !== draft.identity.providerId ||
    !draft.query.collections.includes(draft.identity.collectionId)
  ) {
    throw new Error("The saved scene query context does not match its identity.");
  }
  if (draft.queryFingerprint !== catalogueQueryFingerprintFromRequest(draft.query)) {
    throw new Error("The saved scene query fingerprint does not match its query context.");
  }
  if (
    Date.parse(draft.query.acquisition.end) < Date.parse(draft.query.acquisition.start) ||
    Date.parse(draft.scene.acquisition.end) < Date.parse(draft.scene.acquisition.start)
  ) {
    throw new Error("The saved scene contains an invalid acquisition interval.");
  }
  if (draft.scene.preview !== null) {
    throw new Error("The saved scene contains a preview URL that cannot be restored safely.");
  }
  validateGeometry(draft.scene);
  validateDurableReferences(draft.scene);
  return {
    savedAt: draft.savedAt,
    selection: {
      identity: draft.identity,
      key: catalogueSceneKey(draft.scene),
      scene: draft.scene,
      queryFingerprint: draft.queryFingerprint,
      query: draft.query,
      previewMetadata: draft.previewMetadata,
    },
  };
}
