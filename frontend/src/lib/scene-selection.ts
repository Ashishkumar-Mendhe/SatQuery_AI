import type { CatalogueScene, CatalogueSearchRequest } from "@/lib/catalog-client";

export interface CatalogueSceneIdentity {
  providerId: string;
  collectionId: string;
  itemId: string;
}

export interface SelectedCatalogueScene {
  identity: CatalogueSceneIdentity;
  key: string;
  scene: CatalogueScene;
  queryFingerprint: string;
  query: CatalogueSearchRequest;
  previewMetadata: StoredPreviewMetadata | null;
}

export interface CatalogueSceneContext {
  fingerprint: string;
  isCurrent: boolean;
  scenes: CatalogueScene[];
  query: CatalogueSearchRequest;
  hasMore?: boolean;
}

export type StoredPreviewMetadata = Omit<
  NonNullable<CatalogueScene["preview"]>,
  "href" | "expires_at"
>;

export function safePreviewMetadata(scene: CatalogueScene): StoredPreviewMetadata | null {
  if (!scene.preview) return null;
  const { purpose, access, media_type, width, height, attribution } = scene.preview;
  return { purpose, access, media_type, width, height, attribution };
}

export function catalogueSceneIdentity(scene: CatalogueScene): CatalogueSceneIdentity {
  return {
    providerId: scene.provider.id,
    collectionId: scene.collection.id,
    itemId: scene.provider_asset_id,
  };
}

export function catalogueSceneKey(scene: CatalogueScene): string {
  const identity = catalogueSceneIdentity(scene);
  return JSON.stringify([identity.providerId, identity.collectionId, identity.itemId]);
}

export function catalogueQueryFingerprintFromRequest(query: CatalogueSearchRequest): string {
  return JSON.stringify({
    geometry: query.aoi,
    collectionId: query.collections[0] ?? "",
    startDate: query.acquisition.start.slice(0, 10),
    endDate: query.acquisition.end.slice(0, 10),
    cloudThreshold: query.cloud_cover ? String(query.cloud_cover.max_percent) : "",
  });
}

export function createCatalogueSceneSelection(
  scene: CatalogueScene,
  queryFingerprint: string,
  query: CatalogueSearchRequest,
): SelectedCatalogueScene {
  return {
    identity: catalogueSceneIdentity(scene),
    key: catalogueSceneKey(scene),
    scene,
    queryFingerprint,
    query: { ...query, cursor: null },
    previewMetadata: safePreviewMetadata(scene),
  };
}
