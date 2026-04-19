import type { BuildingProfileInput, BuildingProfileResult } from "../types";

export type RegisterResult =
  | { ok: true; data: BuildingProfileResult }
  | { ok: false; errors: Record<string, string> };

export async function registerBuildingProfile(
  profile: BuildingProfileInput
): Promise<RegisterResult> {
  const res = await fetch("/api/buildings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });

  if (res.ok) {
    return { ok: true, data: (await res.json()) as BuildingProfileResult };
  }

  if (res.status === 400) {
    const body = await res.json();
    const errors = body?.detail?.errors ?? {
      _general: "Validation failed",
    };
    return { ok: false, errors };
  }

  return {
    ok: false,
    errors: { _general: `Unexpected error (${res.status})` },
  };
}
