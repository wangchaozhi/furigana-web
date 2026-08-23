import type { AnnotatedLine, DocumentMeta, LayoutSettings, LyricsSearchResult, OverrideItem, ProjectItem, ProjectSummary, TranslationLanguage, TranslationProvider, TranslationProviderStatus } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const DEFAULT_TIMEOUT_MS = 30_000;
let accessToken = "";

type RequestOptions = RequestInit & { timeoutMs?: number };

export function setAccessToken(token: string | null) {
  accessToken = token || "";
}

async function request(input: RequestInfo | URL, init: RequestOptions = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal: callerSignal, ...requestInit } = init;
  const headers = new Headers(requestInit.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort(callerSignal?.reason);
  if (callerSignal?.aborted) abortFromCaller();
  else callerSignal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await globalThis.fetch(input, { ...requestInit, headers, signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted && !callerSignal?.aborted) {
      throw new Error("请求超时，请稍后重试");
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
    callerSignal?.removeEventListener("abort", abortFromCaller);
  }
}

export async function getAuthConfig(): Promise<{ required: boolean }> {
  return checked<{ required: boolean }>(await request(`${API_BASE}/api/auth/config`, { cache: "no-store" }));
}

export async function getCurrentUser(): Promise<{ id: string; email: string }> {
  return checked<{ id: string; email: string }>(await request(`${API_BASE}/api/auth/me`, { cache: "no-store" }));
}

async function checked<T>(res: Response): Promise<T> {
  if (!res.ok) throw await responseError(res);
  return res.json() as Promise<T>;
}

async function responseError(res: Response): Promise<Error> {
  const body = await res.text();
  try {
    const parsed = JSON.parse(body) as { detail?: string };
    return new Error(parsed.detail || body || `HTTP ${res.status}`);
  } catch {
    return new Error(body || `HTTP ${res.status}`);
  }
}

export async function annotate(text: string, projectId?: number | null): Promise<AnnotatedLine[]> {
  const res = await request(`${API_BASE}/api/annotate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, project_id: projectId || null }),
  });
  const data = await checked<{ lines: AnnotatedLine[] }>(res);
  return data.lines;
}

export async function searchLyrics(track: string, artist = ""): Promise<LyricsSearchResult[]> {
  const params = new URLSearchParams({ track });
  if (artist.trim()) params.set("artist", artist.trim());
  const res = await request(`${API_BASE}/api/lyrics/search?${params}`, { cache: "no-store" });
  const data = await checked<{ results: LyricsSearchResult[] }>(res);
  return data.results;
}

export async function exportDocx(
  meta: DocumentMeta,
  layout: LayoutSettings,
  translationLanguage: TranslationLanguage,
  lines: AnnotatedLine[],
): Promise<Blob> {
  const res = await request(`${API_BASE}/api/export/docx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ meta, layout, translation_language: translationLanguage, lines }),
    timeoutMs: 60_000,
  });
  if (!res.ok) throw await responseError(res);
  return res.blob();
}

export async function getTranslationStatus(): Promise<{ enabled: boolean; providers: TranslationProviderStatus[] }> {
  const res = await request(`${API_BASE}/api/translation/status`, { cache: "no-store" });
  return checked<{ enabled: boolean; providers: TranslationProviderStatus[] }>(res);
}

export async function translateLines(
  lines: string[],
  targetLanguage: Exclude<TranslationLanguage, "none">,
  provider: TranslationProvider,
): Promise<string[]> {
  const res = await request(`${API_BASE}/api/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lines, target_language: targetLanguage, provider }),
    timeoutMs: 90_000,
  });
  const data = await checked<{ translations: string[] }>(res);
  return data.translations;
}

export async function saveOverride(
  surface: string,
  reading: string,
  context: string,
  scope: OverrideItem["scope"] = "sentence",
  projectId?: number | null,
): Promise<OverrideItem> {
  const res = await request(`${API_BASE}/api/overrides`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ surface, reading, context, scope, project_id: projectId || null }),
  });
  return checked<OverrideItem>(res);
}

export async function listOverrides(): Promise<OverrideItem[]> {
  const res = await request(`${API_BASE}/api/overrides`, { cache: "no-store" });
  return checked<OverrideItem[]>(res);
}

export async function deleteOverride(id: number): Promise<void> {
  const res = await request(`${API_BASE}/api/overrides/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw await responseError(res);
}

export async function updateOverride(
  id: number,
  payload: Pick<OverrideItem, "surface" | "reading" | "context" | "scope" | "project_id">,
): Promise<OverrideItem> {
  const res = await request(`${API_BASE}/api/overrides/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return checked<OverrideItem>(res);
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const res = await request(`${API_BASE}/api/projects`, { cache: "no-store" });
  return checked<ProjectSummary[]>(res);
}

export async function getProject(id: number): Promise<ProjectItem> {
  const res = await request(`${API_BASE}/api/projects/${id}`, { cache: "no-store" });
  return checked<ProjectItem>(res);
}

export async function saveProject(payload: {
  title: string;
  artist: string;
  year: string;
  source_text: string;
  layout: LayoutSettings;
  translation_language: TranslationLanguage;
  lines: AnnotatedLine[];
}): Promise<ProjectItem> {
  const res = await request(`${API_BASE}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return checked<ProjectItem>(res);
}

export async function updateProject(
  id: number,
  payload: {
    title: string;
    artist: string;
    year: string;
    source_text: string;
    layout: LayoutSettings;
    translation_language: TranslationLanguage;
    lines: AnnotatedLine[];
  },
): Promise<ProjectItem> {
  const res = await request(`${API_BASE}/api/projects/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return checked<ProjectItem>(res);
}

export async function deleteProject(id: number): Promise<void> {
  const res = await request(`${API_BASE}/api/projects/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw await responseError(res);
}
