import { apiBaseUrl } from "./health-client";

export interface PersistedAoi {
  id: string;
  workspace_id: string | null;
  name: string;
  source: string;
  area_sqkm: number;
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
  bounds: [number, number, number, number];
  validation_status: string;
  created_at: string;
  updated_at: string;
}

export interface PersistedHistory {
  id: string;
  workspace_id: string | null;
  analysis_type: string;
  title: string;
  query_text: string | null;
  status: string;
  result: Record<string, unknown>;
  created_at: string;
}

export async function fetchSavedAois(signal?: AbortSignal): Promise<PersistedAoi[]> {
  try {
    const base = apiBaseUrl();
    const resp = await fetch(`${base}/aois`, { signal });
    if (!resp.ok) return [];
    return (await resp.json()) as PersistedAoi[];
  } catch {
    return [];
  }
}

export async function saveAoiRecord(
  payload: {
    name: string;
    source: string;
    area_sqkm: number;
    geometry: { type: string; coordinates: unknown };
    bounds: number[];
    workspace_id?: string | null;
  },
  signal?: AbortSignal,
): Promise<PersistedAoi | null> {
  try {
    const base = apiBaseUrl();
    const resp = await fetch(`${base}/aois`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
    if (!resp.ok) return null;
    return (await resp.json()) as PersistedAoi;
  } catch {
    return null;
  }
}

export async function deleteSavedAoi(id: string, signal?: AbortSignal): Promise<boolean> {
  try {
    const base = apiBaseUrl();
    const resp = await fetch(`${base}/aois/${id}`, { method: "DELETE", signal });
    return resp.ok;
  } catch {
    return false;
  }
}

export async function fetchAnalysisHistory(signal?: AbortSignal): Promise<PersistedHistory[]> {
  try {
    const base = apiBaseUrl();
    const resp = await fetch(`${base}/history`, { signal });
    if (!resp.ok) return [];
    return (await resp.json()) as PersistedHistory[];
  } catch {
    return [];
  }
}

export async function saveAnalysisHistory(
  payload: {
    analysis_type: string;
    title: string;
    query_text?: string | null;
    result: Record<string, unknown>;
    workspace_id?: string | null;
  },
  signal?: AbortSignal,
): Promise<PersistedHistory | null> {
  try {
    const base = apiBaseUrl();
    const resp = await fetch(`${base}/history`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
    if (!resp.ok) return null;
    return (await resp.json()) as PersistedHistory;
  } catch {
    return null;
  }
}

export async function deleteAnalysisHistory(id: string, signal?: AbortSignal): Promise<boolean> {
  try {
    const base = apiBaseUrl();
    const resp = await fetch(`${base}/history/${id}`, { method: "DELETE", signal });
    return resp.ok;
  } catch {
    return false;
  }
}
