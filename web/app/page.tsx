"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import RubyEditor from "@/components/RubyEditor";
import RubyPreview from "@/components/RubyPreview";
import {
  annotate,
  deleteOverride,
  deleteProject,
  exportDocx,
  getProject,
  listOverrides,
  listProjects,
  saveOverride,
  saveProject,
  updateOverride,
  updateProject,
} from "@/lib/api";
import type { AnnotatedLine, DocumentMeta, OverrideItem, ProjectSummary } from "@/lib/types";

type Selection = { lineIndex: number; segmentIndex: number } | null;

const EMPTY_META: DocumentMeta = { title: "", artist: "", year: "" };
const DRAFT_KEY = "furigana-studio:draft:v1";

export default function Home() {
  const [meta, setMeta] = useState<DocumentMeta>(EMPTY_META);
  const [source, setSource] = useState("");
  const [lines, setLines] = useState<AnnotatedLine[]>([]);
  const [pastLines, setPastLines] = useState<AnnotatedLine[][]>([]);
  const [futureLines, setFutureLines] = useState<AnnotatedLine[][]>([]);
  const [selected, setSelected] = useState<Selection>(null);
  const [busy, setBusy] = useState<"annotate" | "export" | "image" | "save" | null>(null);
  const [message, setMessage] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectPanel, setProjectPanel] = useState(false);
  const [currentProjectId, setCurrentProjectId] = useState<number | null>(null);
  const [overrides, setOverrides] = useState<OverrideItem[]>([]);
  const [overridePanel, setOverridePanel] = useState(false);
  const [editingOverride, setEditingOverride] = useState<OverrideItem | null>(null);
  const documentSheetRef = useRef<HTMLElement>(null);

  const selectedSegment = useMemo(() => {
    if (!selected) return null;
    return lines[selected.lineIndex]?.segments[selected.segmentIndex] || null;
  }, [lines, selected]);

  function setFreshLines(next: AnnotatedLine[]) {
    setLines(next);
    setPastLines([]);
    setFutureLines([]);
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
    try {
      const raw = window.localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw) as {
        meta?: DocumentMeta;
        source?: string;
        lines?: AnnotatedLine[];
        projectId?: number | null;
      };
      if (draft.source || draft.meta?.title) {
        setMeta(draft.meta || EMPTY_META);
        setSource(draft.source || "");
        setFreshLines(draft.lines || []);
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
        JSON.stringify({ meta, source, lines, projectId: currentProjectId }),
      );
    }, 600);
    return () => window.clearTimeout(timer);
  }, [meta, source, lines, currentProjectId]);

  function flash(text: string) {
    setMessage(text);
    window.setTimeout(() => setMessage(""), 2400);
  }

  async function handleAnnotate() {
    if (!source.trim()) return flash("请先粘贴日文文本");
    setBusy("annotate");
    setSelected(null);
    try {
      setFreshLines(await annotate(source, currentProjectId));
      flash("标注完成");
    } catch (error) {
      flash(`标注失败：${error instanceof Error ? error.message : "未知错误"}`);
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
                  : { ...segment, ruby: reading || null },
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
                segment.text === surface ? { ...segment, ruby: normalizedReading } : segment,
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
        setFreshLines(await annotate(source, currentProjectId));
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
        setFreshLines(await annotate(source, currentProjectId));
        setSelected(null);
      }
      flash("规则已修改，当前预览已更新");
    } catch (error) {
      flash(`修改失败：${error instanceof Error ? error.message : "未知错误"}`);
    }
  }

  async function handleExport() {
    if (!lines.length) return flash("请先完成标注");
    setBusy("export");
    try {
      const blob = await exportDocx(meta, lines);
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
    setBusy("image");
    setSelected(null);
    try {
      if (document.fonts?.ready) await document.fonts.ready;
      await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
      const { toPng } = await import("html-to-image");
      const node = documentSheetRef.current;
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
      const payload = { ...meta, source_text: source, lines };
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
    setSource("");
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
            <span>{overrides.length} 条</span>
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

      <footer>
        预览页可直接下载 PNG 或打印；Word 导出使用原生 WordprocessingML <code>w:ruby</code>。
      </footer>

      {message && <div className="toast">{message}</div>}
    </main>
  );
}
