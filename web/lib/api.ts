import type { AnnotatedLine, DocumentMeta, OverrideItem, ProjectItem, ProjectSummary } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function checked<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function annotate(text: string): Promise<AnnotatedLine[]> {
  const res = await fetch(`${API_BASE}/api/annotate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const data = await checked<{ lines: AnnotatedLine[] }>(res);
  return data.lines;
}

export async function exportDocx(meta: DocumentMeta, lines: AnnotatedLine[]): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/export/docx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ meta, lines }),
  });
  if (!res.ok) throw new Error((await res.text()) || `HTTP ${res.status}`);
  return res.blob();
}

export async function saveOverride(surface: string, reading: string, context: string): Promise<OverrideItem> {
  const res = await fetch(`${API_BASE}/api/overrides`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ surface, reading, context }),
  });
  return checked<OverrideItem>(res);
}

export async function listOverrides(): Promise<OverrideItem[]> {
  const res = await fetch(`${API_BASE}/api/overrides`, { cache: "no-store" });
  return checked<OverrideItem[]>(res);
}

export async function deleteOverride(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/overrides/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error((await res.text()) || `HTTP ${res.status}`);
}

export async function updateOverride(
  id: number,
  payload: Pick<OverrideItem, "surface" | "reading" | "context">,
): Promise<OverrideItem> {
  const res = await fetch(`${API_BASE}/api/overrides/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return checked<OverrideItem>(res);
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const res = await fetch(`${API_BASE}/api/projects`, { cache: "no-store" });
  return checked<ProjectSummary[]>(res);
}

export async function getProject(id: number): Promise<ProjectItem> {
  const res = await fetch(`${API_BASE}/api/projects/${id}`, { cache: "no-store" });
  return checked<ProjectItem>(res);
}

export async function saveProject(payload: {
  title: string;
  artist: string;
  year: string;
  source_text: string;
  lines: AnnotatedLine[];
}): Promise<ProjectItem> {
  const res = await fetch(`${API_BASE}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return checked<ProjectItem>(res);
}

export async function deleteProject(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/projects/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error((await res.text()) || `HTTP ${res.status}`);
}
