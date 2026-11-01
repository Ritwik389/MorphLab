export type Pair = {
  id: string;
  name: string;
  source: string;
  target: string;
  description: string;
};
export type Fixture = { name: string; url: string; expected: string };
export type Examples = {
  pairs: Pair[];
  fixtures: Fixture[];
  credits: { name: string; creator: string; license: string; url: string }[];
};
export type System = {
  os: string;
  architecture: string;
  apple_silicon: boolean;
  state: string;
  live_runtime: string | null;
  live_note: string | null;
  active_runtime: string | null;
  fallback_reason: string | null;
  benchmark: { mean_ms: number; precision: string } | null;
};
export type Job = {
  id: string;
  state: string;
  progress: number;
  message: string;
  result: string | null;
  original?: string | null;
  report_url: string | null;
  report: Record<string, unknown>;
};
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({
        detail: "Could not reach MorphLab. Check that the local server is running.",
      }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Check the supplied files and settings.",
    );
  }
  return response.json();
}
export async function assetFile(url: string) {
  const r = await fetch(url);
  if (!r.ok) throw new Error("Could not load example.");
  return new File([await r.blob()], url.split("/").pop() || "example.jpg");
}
