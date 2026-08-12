"use client";

import { useEffect, useState } from "react";
import type { AnnotatedLine, OverrideItem } from "@/lib/types";

type Selection = { lineIndex: number; segmentIndex: number } | null;

type Props = {
  lines: AnnotatedLine[];
  selected: Selection;
  onChange: (reading: string) => void;
  projectId: number | null;
  onSaveOverride: (context: string, reading: string, scope: OverrideItem["scope"]) => Promise<void>;
  onClose: () => void;
};

export default function RubyEditor({ lines, selected, projectId, onChange, onSaveOverride, onClose }: Props) {
  const segment = selected ? lines[selected.lineIndex]?.segments[selected.segmentIndex] : undefined;
  const line = selected ? lines[selected.lineIndex] : undefined;
  const [value, setValue] = useState(segment?.ruby || "");
  const [saving, setSaving] = useState(false);
  const [scope, setScope] = useState<OverrideItem["scope"]>("sentence");

  useEffect(() => {
    setValue(segment?.ruby || "");
  }, [segment?.ruby, selected?.lineIndex, selected?.segmentIndex]);

  if (!segment || !line || !selected) return null;
  const context = line.source;

  async function saveAsRule() {
    setSaving(true);
    try {
      onChange(value.trim());
      await onSaveOverride(context, value.trim(), scope);
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
      {(segment.candidates?.length || 0) > 1 && (
        <div className="candidateBox">
          <div className="candidateHead">
            <span>词典候选</span>
            <span className={`confidence ${segment.confidence || "low"}`}>
              {segment.confidence === "high" ? "高可信" : segment.confidence === "medium" ? "有多种读法" : "请人工确认"}
            </span>
          </div>
          <div className="candidateList">
            {segment.candidates?.map((candidate) => (
              <button
                className={candidate === value ? "candidate active" : "candidate"}
                key={candidate}
                onClick={() => {
                  setValue(candidate);
                  onChange(candidate);
                }}
              >
                {candidate}
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="contextBox">
        <span>规则作用范围</span>
        <select value={scope} onChange={(event) => setScope(event.target.value as OverrideItem["scope"])}>
          <option value="sentence">仅当前句</option>
          <option value="project" disabled={!projectId}>当前项目{projectId ? "" : "（请先保存项目）"}</option>
          <option value="global">所有项目</option>
        </select>
        {scope === "sentence" && <code>{context || "（空行）"}</code>}
      </div>
      <button className="secondaryButton full" disabled={!value.trim() || saving} onClick={saveAsRule}>
        {saving ? "保存中…" : "保存读音规则"}
      </button>
      <p className="helpText">保存后会立即同步当前预览中的相同上下文，以后标注时也会优先使用这个读音。</p>
    </div>
  );
}
