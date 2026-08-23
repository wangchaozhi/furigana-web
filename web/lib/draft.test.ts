import { beforeEach, describe, expect, it, vi } from "vitest";

import { DRAFT_STORAGE_PREFIX, clearDraft, loadDraft, saveDraft, type ProjectDraft } from "./draft";

const draft: ProjectDraft = {
  meta: { title: "测试", artist: "", year: "" },
  source: "明日",
  lines: [{ source: "明日", segments: [{ text: "明日", ruby: "あした" }] }],
  layout: {
    font_size: 18,
    line_spacing: 2.5,
    ruby_scale: 0.55,
    page_margin: 56,
    font_family: "gothic",
    vertical: false,
    columns: 1,
    vertical_row_gap: 24,
  },
  translationLanguage: "none",
  translationProvider: "openai",
  projectId: null,
};

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => { values.delete(key); },
    setItem: (key, value) => { values.set(key, value); },
  };
}

describe("draft storage", () => {
  let storage: Storage;

  beforeEach(() => { storage = createMemoryStorage(); });

  it("round-trips a versioned draft", () => {
    expect(saveDraft(storage, "local", draft)).toBe(true);
    expect(loadDraft(storage, "local")).toMatchObject(draft);
    clearDraft(storage, "local");
    expect(loadDraft(storage, "local")).toBeNull();
  });

  it("removes incompatible drafts", () => {
    storage.setItem(`${DRAFT_STORAGE_PREFIX}:local`, JSON.stringify({ version: 999, source: "旧数据" }));
    expect(loadDraft(storage, "local")).toBeNull();
    expect(storage.length).toBe(0);
  });

  it("reports storage quota failures", () => {
    const storage = { setItem: vi.fn(() => { throw new DOMException("full", "QuotaExceededError"); }) } as unknown as Storage;
    expect(saveDraft(storage, "local", draft)).toBe(false);
  });
});
