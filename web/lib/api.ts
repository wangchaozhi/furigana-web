import type { AnnotatedLine, DocumentMeta, LayoutSettings, LyricsSearchResult, OverrideItem, ProjectItem, ProjectSummary, TranslationLanguage, TranslationProvider, TranslationProviderStatus } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
let accessToken = "";

export function setAccessToken(token: string | null) {
  accessToken = token || "";
}

async function request(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  return globalThis.fetch(input, { ...init, headers });
}

export async function getAuthConfig(): Promise<{ required: boolean }> {
  return checked<{ required: boolean }>(await request(`${API_BASE}/api/auth/config`, { cache: "no-store" }));
}

export async function getCurrentUser(): Promise<{ id: string; email: string }> {
  return checked<{ id: string; email: string }>(await request(`${API_BASE}/api/auth/me`, { cache: "no-store" }));
}

async function checked<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      throw new Error(parsed.detail || body || `HTTP ${res.status}`);
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error(body || `HTTP ${res.status}`);
      throw error;
    }
  }
  return res.json() as Promise<T>;
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
  });
  if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`);
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
  if (!res.ok && res.status !== 204) throw new Error((await res.text()) || `HTTP ${res.status}`);
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
  if (!res.ok && res.status !== 204) throw new Error((await res.text()) || `HTTP ${res.status}`);
}
