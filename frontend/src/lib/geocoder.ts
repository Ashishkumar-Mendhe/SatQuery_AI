const GEOCODER_TIMEOUT_MS = 8_000;
const MINIMUM_REQUEST_INTERVAL_MS = 1_000;
const MAX_CACHE_ENTRIES = 50;

export interface PlaceSearchResult {
  id: string;
  label: string;
  longitude: number;
  latitude: number;
  bounds: [west: number, south: number, east: number, north: number] | null;
}

export class GeocoderError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "GeocoderError";
  }
}

const cache = new Map<string, PlaceSearchResult[]>();
let lastRequestStartedAt = 0;
let requestQueue: Promise<unknown> = Promise.resolve();

function configuredGeocoderUrl(): URL {
  const value = process.env.NEXT_PUBLIC_GEOCODER_URL?.trim();
  if (!value) {
    throw new GeocoderError(
      "Place search is unavailable: no provider is configured. Use coordinates instead.",
    );
  }
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new GeocoderError("Place search is unavailable because its provider URL is invalid.");
  }
  if (url.protocol !== "https:") {
    throw new GeocoderError("Place search requires an HTTPS provider URL.");
  }
  if (url.hostname === "nominatim.openstreetmap.org" || url.username || url.password) {
    throw new GeocoderError(
      "Configure a browser-safe geocoder with an appropriate usage agreement. The public Nominatim endpoint requires application-wide controls this client does not provide.",
    );
  }
  return url;
}

function parseNumber(value: unknown): number | null {
  if (typeof value !== "string" && typeof value !== "number") {
    return null;
  }
  if (typeof value === "string" && !value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseResult(value: unknown, index: number): PlaceSearchResult | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const candidate = value as Record<string, unknown>;
  const longitude = parseNumber(candidate.lon);
  const latitude = parseNumber(candidate.lat);
  if (
    typeof candidate.display_name !== "string" ||
    longitude === null ||
    latitude === null ||
    longitude < -180 ||
    longitude > 180 ||
    latitude < -90 ||
    latitude > 90
  ) {
    return null;
  }

  let bounds: PlaceSearchResult["bounds"] = null;
  if (Array.isArray(candidate.boundingbox) && candidate.boundingbox.length === 4) {
    const [south, north, west, east] = candidate.boundingbox.map(parseNumber);
    if (
      south !== null &&
      north !== null &&
      west !== null &&
      east !== null &&
      west >= -180 &&
      east <= 180 &&
      south >= -85.051129 &&
      north <= 85.051129 &&
      east - west <= 180 &&
      west < east &&
      south < north
    ) {
      bounds = [west, south, east, north];
    }
  }

  return {
    id:
      typeof candidate.place_id === "number"
        ? String(candidate.place_id)
        : `${longitude}-${latitude}-${index}`,
    label: candidate.display_name.trim().slice(0, 240),
    longitude,
    latitude,
    bounds,
  };
}

function enqueue<T>(task: () => Promise<T>): Promise<T> {
  const pending = requestQueue.then(async () => {
    const remaining = MINIMUM_REQUEST_INTERVAL_MS - (Date.now() - lastRequestStartedAt);
    if (remaining > 0) {
      await new Promise((resolve) => setTimeout(resolve, remaining));
    }
    lastRequestStartedAt = Date.now();
    return task();
  });
  requestQueue = pending.catch(() => undefined);
  return pending;
}

export async function searchPlaces(query: string): Promise<PlaceSearchResult[]> {
  const normalizedQuery = query.trim().replace(/\s+/g, " ");
  if (normalizedQuery.length < 2 || normalizedQuery.length > 160) {
    throw new GeocoderError("Enter a place name between 2 and 160 characters.");
  }

  const provider = configuredGeocoderUrl();
  const cacheKey = `${provider.href}:${normalizedQuery.toLocaleLowerCase("en-US")}`;
  const cached = cache.get(cacheKey);
  if (cached) {
    return cached;
  }

  return enqueue(async () => {
    const url = new URL(provider);
    url.searchParams.set("q", normalizedQuery);
    url.searchParams.set("format", "jsonv2");
    url.searchParams.set("limit", "5");
    url.searchParams.set("addressdetails", "0");

    let response: Response;
    try {
      response = await fetch(url, {
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(GEOCODER_TIMEOUT_MS),
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "TimeoutError") {
        throw new GeocoderError("Place search timed out. Try again.");
      }
      throw new GeocoderError("Place search could not reach its provider. Try again.");
    }
    if (!response.ok) {
      throw new GeocoderError(
        `Place search provider returned HTTP ${response.status}. Try again later.`,
      );
    }

    let value: unknown;
    try {
      value = await response.json();
    } catch {
      throw new GeocoderError("Place search returned an unreadable response.");
    }
    if (!Array.isArray(value)) {
      throw new GeocoderError("Place search returned an unexpected response.");
    }
    const results = value
      .slice(0, 5)
      .map(parseResult)
      .filter((result): result is PlaceSearchResult => result !== null && result.label.length > 0);
    if (cache.size >= MAX_CACHE_ENTRIES) {
      const oldestKey = cache.keys().next().value;
      if (typeof oldestKey === "string") {
        cache.delete(oldestKey);
      }
    }
    cache.set(cacheKey, results);
    return results;
  });
}

export function getGeocoderProviderName(): string {
  return process.env.NEXT_PUBLIC_GEOCODER_NAME?.trim().slice(0, 80) || "the configured geocoder";
}

export function isGeocoderConfigured(): boolean {
  try {
    configuredGeocoderUrl();
    return true;
  } catch {
    return false;
  }
}

export function clearGeocoderCacheForTests(): void {
  cache.clear();
  lastRequestStartedAt = 0;
  requestQueue = Promise.resolve();
}
