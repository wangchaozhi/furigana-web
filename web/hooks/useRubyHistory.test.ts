import { describe, expect, it } from "vitest";

import { EMPTY_RUBY_HISTORY, rubyHistoryReducer } from "./useRubyHistory";
import type { AnnotatedLine } from "@/lib/types";

const original: AnnotatedLine[] = [{ source: "明日", segments: [{ text: "明日", ruby: "あす" }] }];
const edited: AnnotatedLine[] = [{ source: "明日", segments: [{ text: "明日", ruby: "あした" }] }];

describe("rubyHistoryReducer", () => {
  it("commits, undoes, and redoes edits", () => {
    const loaded = rubyHistoryReducer(EMPTY_RUBY_HISTORY, { type: "reset", lines: original });
    const committed = rubyHistoryReducer(loaded, { type: "commit", lines: edited });
    const undone = rubyHistoryReducer(committed, { type: "undo" });
    const redone = rubyHistoryReducer(undone, { type: "redo" });

    expect(committed.present).toBe(edited);
    expect(undone.present).toBe(original);
    expect(redone.present).toBe(edited);
  });

  it("replaces translations without adding an undo step", () => {
    const loaded = rubyHistoryReducer(EMPTY_RUBY_HISTORY, { type: "reset", lines: original });
    const replaced = rubyHistoryReducer(loaded, {
      type: "replace",
      update: (lines) => lines.map((line) => ({ ...line, translation: "明天" })),
    });

    expect(replaced.present[0].translation).toBe("明天");
    expect(replaced.past).toHaveLength(0);
  });
});
