"use client";

import { useEffect, useState } from "react";
import type { AnnotatedLine } from "@/lib/types";

type Selection = { lineIndex: number; segmentIndex: number } | null;

type Props = {
  lines: AnnotatedLine[];
  selected: Selection;
  onChange: (reading: string) => void;
  onSaveOverride: (context: string, reading: string) => Promise<void>;
  onClose: () => void;
};

export default function RubyEditor({ lines, selected, onChange, onSaveOverride, onClose }: Props) {
  const segment = selected ? lines[selected.lineIndex]?.segments[selected.segmentIndex] : undefined;
  const line = selected ? lines[selected.lineIndex] : undefined;
  const [value, setValue] = useState(segment?.ruby || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValue(segment?.ruby || "");
  }, [segment?.ruby, selected?.lineIndex, selected?.segmentIndex]);

  if (!segment || !line || !selected) return null;
  const context = line.source;

  async function saveAsRule() {
    setSaving(true);
    try {
      onChange(value.trim());
      await onSaveOverride(context, value.trim());
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rubyEditor">
      <div className="rubyEditorHead">
        <div>
          <span className="eyebrow">当前汉字</span>
          <strong>{segment.text}</strong>
        </div>
        <button className="iconButton" onClick={onClose} aria-label="关闭">×</button>
      </div>
      <label>
        平假名读音
        <input
          autoFocus
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            onChange(event.target.value);
          }}
          placeholder="例如：あした"
        />
      </label>
      <div className="contextBox">
        <span>上下文规则</span>
        <code>{context || "（空行）"}</code>
      </div>
      <button className="secondaryButton full" disabled={!value.trim() || saving} onClick={saveAsRule}>
        {saving ? "保存中…" : "保存为该句读音规则"}
      </button>
      <p className="helpText">保存后会立即同步当前预览中的相同上下文，以后标注时也会优先使用这个读音。</p>
    </div>
  );
}
