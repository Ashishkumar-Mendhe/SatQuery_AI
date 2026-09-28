/**
 * Safe, validated public client configuration.
 *
 * Guaranteed to NEVER expose or require server secrets (API keys, client secrets, database passwords).
 */

export interface PublicAppConfig {
  apiBaseUrl: string;
  environment: "development" | "test" | "staging" | "production";
  contractVersion: string;
  isDemoMode: boolean;
}

export class PublicConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PublicConfigError";
  }
}

export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
  try {
    const parsed = new URL(configured);
    const path = parsed.pathname.replace(/\/+$/, "");
    if (
      !["http:", "https:"].includes(parsed.protocol) ||
      parsed.username ||
      parsed.password ||
      parsed.search ||
      parsed.hash ||
      path !== "/api/v1"
    ) {
      throw new Error("Invalid API path or credentials present");
    }
    return configured.replace(/\/+$/, "");
  } catch {
    throw new PublicConfigError(
      `Invalid NEXT_PUBLIC_API_BASE_URL: "${configured}". Must be a valid HTTP(S) URL ending in /api/v1 without search params or credentials.`,
    );
  }
}

export function appEnvironment(): "development" | "test" | "staging" | "production" {
  const env = process.env.NEXT_PUBLIC_ENVIRONMENT || process.env.NODE_ENV || "development";
  if (["development", "test", "staging", "production"].includes(env)) {
    return env as "development" | "test" | "staging" | "production";
  }
  return "development";
}

export function contractVersion(): string {
  return process.env.NEXT_PUBLIC_CONTRACT_VERSION || "1.0";
}

export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}

export function getPublicConfig(): PublicAppConfig {
  return {
    apiBaseUrl: apiBaseUrl(),
    environment: appEnvironment(),
    contractVersion: contractVersion(),
    isDemoMode: isDemoMode(),
  };
}
