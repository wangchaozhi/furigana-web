import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import RubyEditor from "./RubyEditor";

describe("RubyEditor", () => {
  it("closes with Escape", async () => {
    const onClose = vi.fn();
    render(
      <RubyEditor
        lines={[{ source: "明日", segments: [{ text: "明日", ruby: "あした" }] }]}
        selected={{ lineIndex: 0, segmentIndex: 0 }}
        projectId={null}
        onChange={() => undefined}
        onSaveOverride={async () => undefined}
        onClose={onClose}
      />,
    );

    expect(screen.getByRole("dialog", { name: "编辑振假名" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });
});
