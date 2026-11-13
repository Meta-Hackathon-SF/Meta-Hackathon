/** Production uses the existing Vercel rewrite to Railway, never an implicit fixture. */
export function resolveApiBase(configured: string | undefined, production: boolean): string | undefined {
  const explicit = configured?.trim().replace(/\/+$/, "");
  return explicit || (production ? "/api/v1" : undefined);
}

export function apiBase(): string | undefined {
  return resolveApiBase(import.meta.env.VITE_CONSTELLATIONS_API, import.meta.env.PROD);
}
