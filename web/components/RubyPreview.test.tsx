import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import RubyPreview from "./RubyPreview";
import type { LayoutSettings } from "@/lib/types";

const layout: LayoutSettings = {
  font_size: 18,
  line_spacing: 2.5,
  ruby_scale: 0.55,
  page_margin: 56,
  font_family: "gothic",
  vertical: false,
  columns: 1,
  vertical_row_gap: 24,
};

describe("RubyPreview", () => {
  it("renders document metadata, ruby, and translation", () => {
    render(
      <RubyPreview
        meta={{ title: "明日の歌", artist: "歌手", year: "2026" }}
        layout={layout}
        translationLanguage="zh"
        lines={[{
          source: "明日へ",
          translation: "向着明天",
          segments: [{ text: "明日", ruby: "あした" }, { text: "へ" }],
        }]}
        selected={null}
        onSelect={() => undefined}
      />,
    );

    expect(screen.getByRole("heading", { name: "明日の歌" })).toBeInTheDocument();
    expect(screen.getByText("あした").tagName).toBe("RT");
    expect(screen.getByText("向着明天")).toHaveAttribute("lang", "zh-CN");
  });

  it("selects a ruby segment when clicked", async () => {
    const onSelect = vi.fn();
    render(
      <RubyPreview
        meta={{ title: "", artist: "", year: "" }}
        layout={layout}
        translationLanguage="none"
        lines={[{ source: "明日", segments: [{ text: "明日", ruby: "あした" }] }]}
        selected={null}
        onSelect={onSelect}
      />,
    );

    await userEvent.click(screen.getByText("明日"));
    expect(onSelect).toHaveBeenCalledWith(0, 0);
  });

  it("lets keyboard users select a ruby segment", async () => {
    const onSelect = vi.fn();
    render(
      <RubyPreview
        meta={{ title: "", artist: "", year: "" }}
        layout={layout}
        translationLanguage="none"
        lines={[{ source: "明日", segments: [{ text: "明日", ruby: "あした" }] }]}
        selected={null}
        onSelect={onSelect}
      />,
    );

    const ruby = screen.getByRole("button", { name: /编辑「明日」的读音/ });
    ruby.focus();
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith(0, 0);
  });
});
