import type { AnnotatedLine, DocumentMeta, LayoutSettings, TranslationLanguage, TranslationProvider } from "./types";

export const DRAFT_STORAGE_PREFIX = "furigana-studio:draft:v1";
const DRAFT_SCHEMA_VERSION = 1;

export type ProjectDraft = {
  meta: DocumentMeta;
  source: string;
  lines: AnnotatedLine[];
  layout: LayoutSettings;
  translationLanguage: TranslationLanguage;
  translationProvider: TranslationProvider;
  projectId: number | null;
};

function keyFor(userId: string) {
  return `${DRAFT_STORAGE_PREFIX}:${userId}`;
}

export function loadDraft(storage: Storage, userId: string): Partial<ProjectDraft> | null {
  const key = keyFor(userId);
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ProjectDraft> & { version?: unknown };
    if (parsed.version !== undefined && parsed.version !== DRAFT_SCHEMA_VERSION) {
      storage.removeItem(key);
      return null;
    }
    if (parsed.source !== undefined && typeof parsed.source !== "string") throw new Error("Invalid draft source");
    if (parsed.lines !== undefined && !Array.isArray(parsed.lines)) throw new Error("Invalid draft lines");
    return parsed;
  } catch {
    try {
      storage.removeItem(key);
    } catch {
      // Storage can be unavailable in hardened/private browsing contexts.
    }
    return null;
  }
}

export function saveDraft(storage: Storage, userId: string, draft: ProjectDraft): boolean {
  try {
    storage.setItem(keyFor(userId), JSON.stringify({ version: DRAFT_SCHEMA_VERSION, ...draft }));
    return true;
  } catch {
    return false;
  }
}

export function clearDraft(storage: Storage, userId: string): boolean {
  try {
    storage.removeItem(keyFor(userId));
    return true;
  } catch {
    return false;
  }
}
