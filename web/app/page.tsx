"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import RubyEditor from "@/components/RubyEditor";
import RubyPreview from "@/components/RubyPreview";
import {
  annotate,
  deleteOverride,
  deleteProject,
  exportDocx,
  getTranslationStatus,
  getProject,
  listOverrides,
  listProjects,
  saveOverride,
  saveProject,
  searchLyrics,
  translateLines,
  updateOverride,
  updateProject,
} from "@/lib/api";
import type { AnnotatedLine, DocumentMeta, LayoutSettings, LyricsSearchResult, OverrideItem, ProjectSummary, TranslationLanguage, TranslationProvider, TranslationProviderStatus } from "@/lib/types";

type Selection = { lineIndex: number; segmentIndex: number } | null;

const EMPTY_META: DocumentMeta = { title: "", artist: "", year: "" };
const DEFAULT_LAYOUT: LayoutSettings = {
  font_size: 18,
  line_spacing: 2.5,
  ruby_scale: 0.55,
  page_margin: 56,
  font_family: "gothic",
  vertical: false,
  columns: 1,
};
const DRAFT_KEY = "furigana-studio:draft:v1";

function formatDuration(seconds: number) {
  if (!seconds) return "时长未知";
  const rounded = Math.round(seconds);
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, "0")}`;
}

export default function Home() {
  const [meta, setMeta] = useState<DocumentMeta>(EMPTY_META);
  const [layout, setLayout] = useState<LayoutSettings>(DEFAULT_LAYOUT);
  const [translationLanguage, setTranslationLanguage] = useState<TranslationLanguage>("none");
  const [translationProvider, setTranslationProvider] = useState<TranslationProvider>("openai");
  const [translationStatus, setTranslationStatus] = useState<{ enabled: boolean; providers: TranslationProviderStatus[] } | null>(null);
  const [source, setSource] = useState("");
  const [lyricsTrack, setLyricsTrack] = useState("");
  const [lyricsArtist, setLyricsArtist] = useState("");
  const [lyricsResults, setLyricsResults] = useState<LyricsSearchResult[]>([]);
  const [lyricsSearched, setLyricsSearched] = useState(false);
  const [lines, setLines] = useState<AnnotatedLine[]>([]);
  const [pastLines, setPastLines] = useState<AnnotatedLine[][]>([]);
  const [futureLines, setFutureLines] = useState<AnnotatedLine[][]>([]);
  const [selected, setSelected] = useState<Selection>(null);
  const [busy, setBusy] = useState<"annotate" | "lyrics" | "translate" | "export" | "image" | "save" | null>(null);
  const [message, setMessage] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectPanel, setProjectPanel] = useState(false);
  const [currentProjectId, setCurrentProjectId] = useState<number | null>(null);
  const [overrides, setOverrides] = useState<OverrideItem[]>([]);
  const [overridePanel, setOverridePanel] = useState(false);
  const [layoutPanel, setLayoutPanel] = useState(false);
  const [editingOverride, setEditingOverride] = useState<OverrideItem | null>(null);
  const documentSheetRef = useRef<HTMLElement>(null);
  const ruleImportRef = useRef<HTMLInputElement>(null);

  const selectedSegment = useMemo(() => {
    if (!selected) return null;
    return lines[selected.lineIndex]?.segments[selected.segmentIndex] || null;
  }, [lines, selected]);

  function setFreshLines(next: AnnotatedLine[]) {
    setLines(next);
    setPastLines([]);
    setFutureLines([]);
  }

  function preserveTranslations(next: AnnotatedLine[]) {
    return next.map((line, index) => ({
      ...line,
      translation: lines[index]?.source === line.source ? (lines[index].translation || "") : "",
    }));
  }

  function undoRubyEdit() {
    if (!pastLines.length) return;
    const previous = pastLines[pastLines.length - 1];
    setPastLines(pastLines.slice(0, -1));
    setFutureLines((future) => [lines, ...future].slice(0, 50));
    setLines(previous);
    setSelected(null);
  }

  function redoRubyEdit() {
    if (!futureLines.length) return;
    const next = futureLines[0];
    setFutureLines(futureLines.slice(1));
    setPastLines((past) => [...past.slice(-49), lines]);
    setLines(next);
    setSelected(null);
  }

  async function refreshProjects() {
    try {
      setProjects(await listProjects());
    } catch {
      // Project history is optional; do not block the primary workflow.
    }
  }

  async function refreshOverrides() {
    try {
      setOverrides(await listOverrides());
    } catch {
      // Reading rules are optional; do not block annotation if the list cannot load.
    }
  }

  useEffect(() => {
    refreshProjects();
    refreshOverrides();
    getTranslationStatus().then(setTranslationStatus).catch(() => setTranslationStatus(null));
    try {
      const raw = window.localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw) as {
        meta?: DocumentMeta;
        source?: string;
        lines?: AnnotatedLine[];
        layout?: LayoutSettings;
        translationLanguage?: TranslationLanguage;
        translationProvider?: TranslationProvider;
        projectId?: number | null;
      };
      if (draft.source || draft.meta?.title) {
        setMeta(draft.meta || EMPTY_META);
        setSource(draft.source || "");
        setFreshLines(draft.lines || []);
        setLayout({ ...DEFAULT_LAYOUT, ...draft.layout });
        setTranslationLanguage(draft.translationLanguage || "none");
        setTranslationProvider(draft.translationProvider || "openai");
        setCurrentProjectId(draft.projectId || null);
        flash("已恢复上次未完成的草稿");
      }
    } catch {
      window.localStorage.removeItem(DRAFT_KEY);
    }
  }, []);

  useEffect(() => {
    function handleHistoryShortcut(event: KeyboardEvent) {
      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();
      if (key === "z" && !event.shiftKey && pastLines.length) {
        event.preventDefault();
        undoRubyEdit();
      } else if ((key === "y" || (key === "z" && event.shiftKey)) && futureLines.length) {
        event.preventDefault();
        redoRubyEdit();
      }
    }
    window.addEventListener("keydown", handleHistoryShortcut);
    return () => window.removeEventListener("keydown", handleHistoryShortcut);
  }, [pastLines, futureLines, lines]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (!source && !meta.title && !meta.artist && !meta.year && !lines.length) {
        window.localStorage.removeItem(DRAFT_KEY);
        return;
      }
      window.localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({ meta, layout, translationLanguage, translationProvider, source, lines, projectId: currentProjectId }),
      );
    }, 600);
    return () => window.clearTimeout(timer);
  }, [meta, layout, translationLanguage, translationProvider, source, lines, currentProjectId]);

  function flash(text: string) {
    setMessage(text);
    window.setTimeout(() => setMessage(""), 2400);
  }

  async function handleLyricsSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const track = lyricsTrack.trim();
    if (!track) return flash("请输入歌曲名");
    setBusy("lyrics");
    setLyricsSearched(false);
    try {
      const results = await searchLyrics(track, lyricsArtist);
      setLyricsResults(results);
      setLyricsSearched(true);
      flash(results.length ? `找到 ${results.length} 个歌词版本` : "LRCLIB 暂无匹配歌词");
    } catch (error) {
      setLyricsResults([]);
      setLyricsSearched(true);
      flash(`歌词搜索失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  function importLyrics(result: LyricsSearchResult) {
    if (
      source.trim()
      && source.trim() !== result.plain_lyrics.trim()
      && !window.confirm("导入歌词会覆盖当前原文，是否继续？")
    ) return;
    setSource(result.plain_lyrics.trim());
    setMeta({ title: result.track_name, artist: result.artist_name, year: "" });
    setFreshLines([]);
    setSelected(null);
    setCurrentProjectId(null);
    flash(`已导入《${result.track_name}》，可以开始自动标注`);
  }

  async function handleAnnotate() {
    if (!source.trim()) return flash("请先粘贴日文文本");
    setBusy("annotate");
    setSelected(null);
    try {
      setFreshLines(preserveTranslations(await annotate(source, currentProjectId)));
      flash("标注完成");
    } catch (error) {
      flash(`标注失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  function updateTranslation(lineIndex: number, translation: string) {
    setLines((current) =>
      current.map((line, index) => index === lineIndex ? { ...line, translation } : line),
    );
  }

  async function handleTranslate(mode: "empty" | "all") {
    if (translationLanguage === "none") return flash("请先选择中文或英文翻译");
    if (!lines.length) return flash("请先完成振假名标注");
    const selectedProvider = translationStatus?.providers.find((item) => item.id === translationProvider);
    if (!selectedProvider?.configured) return flash(`${selectedProvider?.label || "所选翻译引擎"}尚未配置`);
    const targets = lines.map((line, index) => mode === "all" || !line.translation?.trim() ? index : -1)
      .filter((index) => index >= 0);
    if (!targets.length) return flash("没有需要翻译的空白行");
    setBusy("translate");
    try {
      const sourceLines = targets.map((index) => lines[index].source);
      const translated = await translateLines(sourceLines, translationLanguage, translationProvider);
      setLines((current) => current.map((line, index) => {
        const position = targets.indexOf(index);
        return position >= 0 ? { ...line, translation: translated[position] || "" } : line;
      }));
      flash(`已完成 ${targets.length} 行${translationLanguage === "zh" ? "中文" : "英文"}翻译`);
    } catch (error) {
      flash(`翻译失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  function updateSelectedRuby(reading: string) {
    if (!selected) return;
    if (selectedSegment?.ruby === (reading || null)) return;
    const next = lines.map((line, lineIndex) =>
        lineIndex !== selected.lineIndex
          ? line
          : {
              ...line,
              segments: line.segments.map((segment, segmentIndex) =>
                segmentIndex !== selected.segmentIndex
                  ? segment
                  : {
                      ...segment,
                      ruby: reading || null,
                      candidates: reading
                        ? [reading, ...(segment.candidates || []).filter((item) => item !== reading)]
                        : segment.candidates,
                      confidence: reading ? "high" : segment.confidence,
                    },
              ),
            },
      );
    setPastLines((past) => [...past.slice(-49), lines]);
    setFutureLines([]);
    setLines(next);
  }

  async function handleSaveOverride(context: string, reading: string, scope: OverrideItem["scope"]) {
    if (!selected || !selectedSegment?.text || !reading) return;
    const surface = selectedSegment.text;
    const normalizedReading = reading.trim();
    await saveOverride(surface, normalizedReading, context, scope, currentProjectId);

    // Keep all matching occurrences in the current preview in sync immediately.
    setFreshLines(
      lines.map((line) =>
        scope === "sentence" && context && !line.source.includes(context)
          ? line
          : {
              ...line,
              segments: line.segments.map((segment) =>
                segment.text === surface
                  ? {
                      ...segment,
                      ruby: normalizedReading,
                      candidates: [normalizedReading, ...(segment.candidates || []).filter((item) => item !== normalizedReading)],
                      confidence: "high",
                    }
                  : segment,
              ),
            },
      ),
    );
    await refreshOverrides();
    flash(`已保存「${surface} → ${normalizedReading}」，当前预览已同步`);
  }

  async function removeOverride(id: number) {
    try {
      await deleteOverride(id);
      await refreshOverrides();
      if (source.trim() && lines.length) {
        setFreshLines(preserveTranslations(await annotate(source, currentProjectId)));
        setSelected(null);
      }
      flash("规则已删除，当前预览已更新");
    } catch (error) {
      flash(`删除失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  async function commitOverrideEdit() {
    if (!editingOverride?.surface.trim() || !editingOverride.reading.trim()) return;
    try {
      await updateOverride(editingOverride.id, {
        surface: editingOverride.surface.trim(),
        reading: editingOverride.reading.trim(),
        context: editingOverride.context.trim(),
        scope: editingOverride.scope,
        project_id: editingOverride.scope === "project" ? editingOverride.project_id : null,
      });
      setEditingOverride(null);
      await refreshOverrides();
      if (source.trim() && lines.length) {
        setFreshLines(preserveTranslations(await annotate(source, currentProjectId)));
        setSelected(null);
      }
      flash("规则已修改，当前预览已更新");
    } catch (error) {
      flash(`修改失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  function exportRules() {
    const payload = {
      version: 1,
      exported_at: new Date().toISOString(),
      rules: overrides.map(({ surface, reading, context, scope }) => ({ surface, reading, context, scope })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `furigana-rules-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    flash(`已导出 ${overrides.length} 条规则`);
  }

  async function importRules(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const data = JSON.parse(await file.text()) as { version?: unknown; rules?: unknown };
      if (data.version !== 1 || !Array.isArray(data.rules) || data.rules.length > 5000) {
        throw new Error("文件版本不支持或规则数量超过 5000 条");
      }
      let imported = 0;
      let skipped = 0;
      for (const raw of data.rules) {
        if (!raw || typeof raw !== "object") throw new Error("规则格式不正确");
        const rule = raw as Record<string, unknown>;
        const scope = rule.scope;
        if (
          typeof rule.surface !== "string" || !rule.surface.trim() ||
          typeof rule.reading !== "string" || !rule.reading.trim() ||
          typeof rule.context !== "string" ||
          (scope !== "sentence" && scope !== "project" && scope !== "global")
        ) {
          throw new Error("规则包含无效字段");
        }
        if (scope === "project" && !currentProjectId) {
          skipped += 1;
          continue;
        }
        await saveOverride(
          rule.surface.trim(),
          rule.reading.trim(),
          rule.context,
          scope,
          scope === "project" ? currentProjectId : null,
        );
        imported += 1;
      }
      await refreshOverrides();
      if (source.trim() && lines.length) setFreshLines(preserveTranslations(await annotate(source, currentProjectId)));
      flash(`已导入 ${imported} 条规则${skipped ? `，跳过 ${skipped} 条项目规则` : ""}`);
    } catch (error) {
      flash(`导入失败：${error instanceof Error ? error.message : "文件无法读取"}`);
    }
  }

  async function handleExport() {
    if (!lines.length) return flash("请先完成标注");
    setBusy("export");
    try {
      const blob = await exportDocx(meta, layout, translationLanguage, lines);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${meta.title.trim() || "furigana"}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      flash("Word 已生成");
    } catch (error) {
      flash(`导出失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  function safeFileName(name: string) {
    return (name.trim() || "furigana")
      .replace(/[\\/:*?"<>|]/g, "_")
      .replace(/\s+/g, " ")
      .slice(0, 120);
  }

  async function handleDownloadImage() {
    if (!lines.length || !documentSheetRef.current) return flash("请先完成标注");
    const node = documentSheetRef.current;
    setBusy("image");
    setSelected(null);
    try {
      if (document.fonts?.ready) await document.fonts.ready;
      await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
      const { toPng } = await import("html-to-image");
      node.classList.add("exporting");
      const dataUrl = await toPng(node, {
        cacheBust: true,
        pixelRatio: 2,
        backgroundColor: "#ffffff",
      });
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `${safeFileName(meta.title)}.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      flash("PNG 图片已生成");
    } catch (error) {
      flash(`图片生成失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      node.classList.remove("exporting");
      setBusy(null);
    }
  }

  function handlePrint() {
    if (!lines.length) return flash("请先完成标注");
    setSelected(null);
    window.setTimeout(() => window.print(), 0);
  }

  async function handleSaveProject() {
    if (!source.trim() || !lines.length) return flash("请先输入并标注文本");
    setBusy("save");
    try {
      const payload = { ...meta, layout, translation_language: translationLanguage, source_text: source, lines };
      const project = currentProjectId
        ? await updateProject(currentProjectId, payload)
        : await saveProject(payload);
      setCurrentProjectId(project.id);
      await refreshProjects();
      flash(currentProjectId ? "项目已更新" : "项目已保存");
    } catch (error) {
      flash(`保存失败：${error instanceof Error ? error.message : "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  async function loadProject(id: number) {
    try {
      const project = await getProject(id);
      setMeta({ title: project.title, artist: project.artist, year: project.year });
      setLayout({ ...DEFAULT_LAYOUT, ...project.layout });
      setTranslationLanguage(project.translation_language || "none");
      setSource(project.source_text);
      setFreshLines(project.lines);
      setCurrentProjectId(project.id);
      setSelected(null);
      setProjectPanel(false);
      flash("项目已载入");
    } catch (error) {
      flash(`载入失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  async function removeProject(id: number) {
    await deleteProject(id);
    if (currentProjectId === id) setCurrentProjectId(null);
    await refreshProjects();
  }

  function reset() {
    setMeta(EMPTY_META);
    setLayout(DEFAULT_LAYOUT);
    setTranslationLanguage("none");
    setSource("");
    setLyricsTrack("");
    setLyricsArtist("");
    setLyricsResults([]);
    setLyricsSearched(false);
    setFreshLines([]);
    setSelected(null);
    setCurrentProjectId(null);
    window.localStorage.removeItem(DRAFT_KEY);
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <div className="brandMark">振</div>
          <div>
            <h1>Furigana Studio</h1>
            <p>只标汉字 · PNG 图片 · A4 打印 · Word Ruby</p>
          </div>
        </div>
        <div className="topActions">
          <button className="ghostButton" onClick={() => setProjectPanel((x) => !x)}>历史项目</button>
          <button
            className="ghostButton"
            onClick={() => {
              setOverridePanel((x) => !x);
              if (!overridePanel) refreshOverrides();
            }}
          >
            读音规则{overrides.length ? ` (${overrides.length})` : ""}
          </button>
          <button className="ghostButton" onClick={() => setLayoutPanel((value) => !value)}>排版设置</button>
          <button className="ghostButton" onClick={reset}>新建</button>
          <button className="secondaryButton" disabled={!lines.length || busy === "save"} onClick={handleSaveProject}>
            {busy === "save" ? "保存中…" : currentProjectId ? "更新项目" : "保存项目"}
          </button>
          <button className="ghostButton" disabled={!lines.length} onClick={handlePrint}>
            打印
          </button>
          <button className="secondaryButton" disabled={!lines.length || busy === "image"} onClick={handleDownloadImage}>
            {busy === "image" ? "生成中…" : "下载 PNG"}
          </button>
          <button className="primaryButton" disabled={!lines.length || busy === "export"} onClick={handleExport}>
            {busy === "export" ? "生成中…" : "导出 Word"}
          </button>
        </div>
      </header>

      {projectPanel && (
        <section className="projectPanel">
          <div className="panelTitle">
            <strong>历史项目</strong>
            <span>{projects.length} 个</span>
          </div>
          {projects.length === 0 ? (
            <div className="emptySmall">还没有保存过项目。</div>
          ) : (
            <div className="projectList">
              {projects.map((project) => (
                <div className="projectItem" key={project.id}>
                  <button className="projectOpen" onClick={() => loadProject(project.id)}>
                    <strong>{project.title || "未命名项目"}</strong>
                    <span>{[project.artist, project.year].filter(Boolean).join(" · ") || "无元数据"}</span>
                  </button>
                  <button className="deleteButton" onClick={() => removeProject(project.id)}>删除</button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {overridePanel && (
        <section className="rulePanel card">
          <div className="panelTitle rulePanelTitle">
            <div>
              <strong>读音规则</strong>
              <span>保存的上下文规则会优先于词典读音</span>
            </div>
            <div className="rulePanelTools">
              <span>{overrides.length} 条</span>
              <button className="ghostButton compactButton" disabled={!overrides.length} onClick={exportRules}>导出 JSON</button>
              <button className="secondaryButton compactButton" onClick={() => ruleImportRef.current?.click()}>导入 JSON</button>
              <input
                ref={ruleImportRef}
                className="visuallyHidden"
                type="file"
                accept="application/json,.json"
                onChange={importRules}
              />
            </div>
          </div>
          {overrides.length === 0 ? (
            <div className="emptyRule">还没有保存过读音规则。</div>
          ) : (
            <div className="ruleList">
              {overrides.map((item) => (
                <div className="ruleItem" key={item.id}>
                  {editingOverride?.id === item.id ? (
                    <>
                      <div className="ruleEditFields">
                        <input
                          aria-label="规则文字"
                          value={editingOverride.surface}
                          onChange={(event) => setEditingOverride({ ...editingOverride, surface: event.target.value })}
                        />
                        <span>→</span>
                        <input
                          aria-label="规则读音"
                          value={editingOverride.reading}
                          onChange={(event) => setEditingOverride({ ...editingOverride, reading: event.target.value })}
                        />
                      </div>
                      <input
                        className="ruleContextInput"
                        aria-label="规则上下文"
                        value={editingOverride.context}
                        onChange={(event) => setEditingOverride({ ...editingOverride, context: event.target.value })}
                        placeholder="所有上下文"
                      />
                      <select
                        className="ruleScopeSelect"
                        aria-label="规则作用范围"
                        value={editingOverride.scope}
                        onChange={(event) => {
                          const scope = event.target.value as OverrideItem["scope"];
                          setEditingOverride({
                            ...editingOverride,
                            scope,
                            project_id: scope === "project" ? (editingOverride.project_id || currentProjectId) : null,
                          });
                        }}
                      >
                        <option value="sentence">仅当前句</option>
                        <option value="project" disabled={!editingOverride.project_id && !currentProjectId}>当前项目</option>
                        <option value="global">所有项目</option>
                      </select>
                      <div className="ruleActions">
                        <button className="secondaryButton compactButton" onClick={commitOverrideEdit}>保存</button>
                        <button className="ghostButton compactButton" onClick={() => setEditingOverride(null)}>取消</button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="ruleReading">
                        <strong>{item.surface}</strong>
                        <span>→</span>
                        <strong>{item.reading}</strong>
                      </div>
                      <div className="ruleContext" title={item.context || "所有上下文"}>
                        <span className="scopeBadge">
                          {item.scope === "sentence" ? "当前句" : item.scope === "project" ? `项目 #${item.project_id}` : "全局"}
                        </span>
                        {item.scope === "sentence" ? item.context : item.scope === "project" ? "当前项目内生效" : "所有项目生效"}
                      </div>
                      <div className="ruleActions">
                        <button className="ghostButton compactButton" onClick={() => setEditingOverride(item)}>编辑</button>
                        <button className="deleteButton" onClick={() => removeOverride(item.id)}>删除</button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {layoutPanel && (
        <section className="layoutPanel card">
          <div className="panelTitle">
            <div>
              <strong>排版设置</strong>
              <span>同步应用到预览、PNG、打印和 Word</span>
            </div>
            <button className="ghostButton compactButton" onClick={() => setLayout(DEFAULT_LAYOUT)}>恢复默认</button>
          </div>
          <div className="layoutGrid">
            <label>
              正文字号 <output>{layout.font_size}px</output>
              <input type="range" min="12" max="32" value={layout.font_size} onChange={(event) => setLayout({ ...layout, font_size: Number(event.target.value) })} />
            </label>
            <label>
              行距 <output>{layout.line_spacing.toFixed(1)}</output>
              <input type="range" min="1.2" max="4" step="0.1" value={layout.line_spacing} onChange={(event) => setLayout({ ...layout, line_spacing: Number(event.target.value) })} />
            </label>
            <label>
              振假名大小 <output>{Math.round(layout.ruby_scale * 100)}%</output>
              <input type="range" min="0.35" max="0.9" step="0.05" value={layout.ruby_scale} onChange={(event) => setLayout({ ...layout, ruby_scale: Number(event.target.value) })} />
            </label>
            <label>
              页边距 <output>{layout.page_margin}px</output>
              <input type="range" min="16" max="96" value={layout.page_margin} onChange={(event) => setLayout({ ...layout, page_margin: Number(event.target.value) })} />
            </label>
            <label>
              字体
              <select value={layout.font_family} onChange={(event) => setLayout({ ...layout, font_family: event.target.value as LayoutSettings["font_family"] })}>
                <option value="gothic">日文黑体</option>
                <option value="mincho">日文明朝体</option>
                <option value="system">系统字体</option>
              </select>
            </label>
            <label>
              排列方向
              <select
                value={layout.vertical ? "vertical" : "horizontal"}
                onChange={(event) => {
                  const vertical = event.target.value === "vertical";
                  setLayout({ ...layout, vertical, columns: vertical ? 1 : layout.columns });
                }}
              >
                <option value="horizontal">横排</option>
                <option value="vertical">竖排</option>
              </select>
            </label>
            <label>
              正文分栏
              <select
                value={layout.columns}
                disabled={layout.vertical}
                onChange={(event) => setLayout({ ...layout, columns: Number(event.target.value) as LayoutSettings["columns"] })}
              >
                <option value={1}>单栏</option>
                <option value={2}>双栏</option>
              </select>
            </label>
          </div>
        </section>
      )}

      <section className="lyricsLookup card">
        <div className="lyricsLookupHead">
          <div>
            <span className="eyebrow">LYRICS LOOKUP</span>
            <h2>获取歌词</h2>
            <p>从 LRCLIB 搜索并导入；没有合适结果时可转到 Google 查找后手工粘贴。</p>
          </div>
          <span className="sourceBadge">LRCLIB</span>
        </div>
        <form className="lyricsSearchForm" onSubmit={handleLyricsSearch}>
          <label>
            歌曲名
            <input
              value={lyricsTrack}
              onChange={(event) => setLyricsTrack(event.target.value)}
              placeholder="例如：ライトダンス"
            />
          </label>
          <label>
            歌手（可选）
            <input
              value={lyricsArtist}
              onChange={(event) => setLyricsArtist(event.target.value)}
              placeholder="例如：サカナクション"
            />
          </label>
          <div className="lyricsSearchActions">
            <button className="primaryButton" type="submit" disabled={!lyricsTrack.trim() || busy === "lyrics"}>
              {busy === "lyrics" ? "搜索中…" : "搜索歌词"}
            </button>
            {lyricsTrack.trim() ? (
              <a
                className="ghostButton googleLyricsLink"
                href={`https://www.google.com/search?q=${encodeURIComponent(`${lyricsTrack.trim()} ${lyricsArtist.trim()} 歌詞`.trim())}`}
                target="_blank"
                rel="noreferrer"
              >
                Google 备用搜索 ↗
              </a>
            ) : (
              <button className="ghostButton" type="button" disabled>Google 备用搜索 ↗</button>
            )}
          </div>
        </form>

        {lyricsResults.length > 0 ? (
          <div className="lyricsResults" aria-live="polite">
            {lyricsResults.map((result, index) => (
              <article className="lyricsResult" key={result.id}>
                <div className="lyricsResultRank">{String(index + 1).padStart(2, "0")}</div>
                <div className="lyricsResultInfo">
                  <strong>{result.track_name}</strong>
                  <span>{result.artist_name || "未知歌手"}</span>
                  <small>
                    {[result.album_name, formatDuration(result.duration), result.has_synced_lyrics ? "含时间轴" : "纯文本"]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                  <details>
                    <summary>预览歌词</summary>
                    <pre>{result.plain_lyrics}</pre>
                  </details>
                </div>
                <button className="secondaryButton compactButton" type="button" onClick={() => importLyrics(result)}>
                  导入原文
                </button>
              </article>
            ))}
          </div>
        ) : lyricsSearched && busy !== "lyrics" ? (
          <p className="lyricsEmpty">没有找到可导入的歌词，可以使用 Google 备用搜索后粘贴到原文框。</p>
        ) : null}
      </section>

      <section className="metaGrid card">
        <label>
          标题
          <input value={meta.title} onChange={(e) => setMeta({ ...meta, title: e.target.value })} placeholder="Light Dance (ライトダンス)" />
        </label>
        <label>
          歌手 / 作者
          <input value={meta.artist} onChange={(e) => setMeta({ ...meta, artist: e.target.value })} placeholder="Sakanaction" />
        </label>
        <label>
          年份
          <input value={meta.year} onChange={(e) => setMeta({ ...meta, year: e.target.value })} placeholder="2009" />
        </label>
      </section>

      <section className="workspace">
        <div className="card editorCard">
          <div className="cardHead">
            <div>
              <span className="eyebrow">01 / INPUT</span>
              <h2>原文</h2>
            </div>
            <button className="primaryButton" disabled={busy === "annotate"} onClick={handleAnnotate}>
              {busy === "annotate" ? "分析中…" : lines.length ? "重新标注" : "自动标注"}
            </button>
          </div>
          <textarea
            className="sourceInput"
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              if (lines.length) {
                setFreshLines([]);
                setSelected(null);
              }
            }}
            placeholder={"粘贴日文歌词或文章…\n例如：でも明日が見えなくて"}
            spellCheck={false}
          />
          <div className="footNote">Sudachi 负责词形与读音；现有假名会作为锚点，只给汉字部分生成振假名。</div>
        </div>

        <div className="card previewCard">
          <div className="cardHead">
            <div>
              <span className="eyebrow">02 / REVIEW</span>
              <h2>振假名预览</h2>
            </div>
            <div className="reviewActions">
              <button className="ghostButton compactButton" disabled={!pastLines.length} onClick={undoRubyEdit}>撤销</button>
              <button className="ghostButton compactButton" disabled={!futureLines.length} onClick={redoRubyEdit}>重做</button>
              <span className="hintPill">点击振假名可修改</span>
            </div>
          </div>
          <RubyPreview
            ref={documentSheetRef}
            meta={meta}
            layout={layout}
            translationLanguage={translationLanguage}
            lines={lines}
            selected={selected}
            onSelect={(lineIndex, segmentIndex) => setSelected({ lineIndex, segmentIndex })}
          />
          {selected && (
            <RubyEditor
              lines={lines}
              selected={selected}
              projectId={currentProjectId}
              onChange={updateSelectedRuby}
              onSaveOverride={handleSaveOverride}
              onClose={() => setSelected(null)}
            />
          )}
        </div>
      </section>

      <section className="translationPanel card">
        <div className="translationToolbar">
          <div>
            <span className="eyebrow">TRANSLATION</span>
            <h2>逐句翻译</h2>
          </div>
          <label className="inlineField">
            译文语言
            <select
              value={translationLanguage}
              onChange={(event) => setTranslationLanguage(event.target.value as TranslationLanguage)}
            >
              <option value="none">不显示</option>
              <option value="zh">中文</option>
              <option value="en">英文</option>
            </select>
          </label>
          <label className="inlineField">
            翻译引擎
            <select value={translationProvider} onChange={(event) => setTranslationProvider(event.target.value as TranslationProvider)}>
              {(translationStatus?.providers || []).map((provider) => (
                <option key={provider.id} value={provider.id}>{provider.label}{provider.configured ? "" : "（未配置）"}</option>
              ))}
            </select>
          </label>
          <div className="translationActions">
            <button
              className="secondaryButton compactButton"
              disabled={translationLanguage === "none" || !lines.length || busy === "translate" || !translationStatus?.providers.find((item) => item.id === translationProvider)?.configured}
              onClick={() => handleTranslate("empty")}
            >
              {busy === "translate" ? "翻译中…" : "翻译空白行"}
            </button>
            <button
              className="ghostButton compactButton"
              disabled={translationLanguage === "none" || !lines.length || busy === "translate" || !translationStatus?.providers.find((item) => item.id === translationProvider)?.configured}
              onClick={() => handleTranslate("all")}
            >
              重新翻译全部
            </button>
          </div>
        </div>
        {translationLanguage === "none" ? (
          <p className="translationHint">选择中文或英文后，可逐句手工填写，译文会显示在日文下方。</p>
        ) : !lines.length ? (
          <p className="translationHint">完成自动标注后即可逐句编辑译文。</p>
        ) : (
          <>
            <div className="translationList">
              {lines.map((line, index) => (
                <label className="translationItem" key={`${index}-${line.source}`}>
                  <span>{line.source || "（空行）"}</span>
                  <textarea
                    value={line.translation || ""}
                    onChange={(event) => updateTranslation(index, event.target.value)}
                    placeholder={translationLanguage === "zh" ? "输入中文翻译…" : "Enter English translation…"}
                    rows={1}
                  />
                </label>
              ))}
            </div>
            <p className="translationHint">
              {translationStatus?.providers.find((item) => item.id === translationProvider)?.configured
                ? `已启用${translationStatus.providers.find((item) => item.id === translationProvider)?.label}，所有译文都可以继续手动修改。`
                : "所选翻译引擎尚未配置；仍可手动填写。请在 API 服务中设置对应环境变量。"}
            </p>
          </>
        )}
      </section>

      <footer>
        预览页可直接下载 PNG 或打印；Word 导出使用原生 WordprocessingML <code>w:ruby</code>。
      </footer>

      {message && <div className="toast">{message}</div>}
      <style>{`@media print { @page { margin: ${(layout.page_margin * 0.32).toFixed(1)}mm; } }`}</style>
    </main>
  );
}
