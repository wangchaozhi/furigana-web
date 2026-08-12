"use client";

import { forwardRef, type CSSProperties } from "react";
import type { AnnotatedLine, DocumentMeta, LayoutSettings } from "@/lib/types";

type Selection = { lineIndex: number; segmentIndex: number } | null;

type Props = {
  meta: DocumentMeta;
  layout: LayoutSettings;
  lines: AnnotatedLine[];
  selected: Selection;
  onSelect: (lineIndex: number, segmentIndex: number) => void;
};

const RubyPreview = forwardRef<HTMLElement, Props>(function RubyPreview(
  { meta, layout, lines, selected, onSelect },
  ref,
) {
  if (!lines.length) {
    return <div className="emptyState">标注后会在这里预览。只给汉字显示振假名。</div>;
  }

  const byline = [meta.artist.trim() ? `Song by ${meta.artist.trim()}` : "", meta.year.trim()]
    .filter(Boolean)
    .join(" · ");
  const fonts = {
    gothic: '"Yu Gothic", "Hiragino Kaku Gothic ProN", sans-serif',
    mincho: '"Yu Mincho", "Hiragino Mincho ProN", serif',
    system: 'Inter, ui-sans-serif, system-ui, sans-serif',
  };
  const documentStyle = {
    "--doc-font-size": `${layout.font_size}px`,
    "--doc-line-height": String(layout.line_spacing),
    "--doc-ruby-size": `${layout.ruby_scale}em`,
    "--doc-margin": `${layout.page_margin}px`,
    "--doc-font-family": fonts[layout.font_family],
  } as CSSProperties;

  return (
    <div className="previewScroll">
      <article className="documentSheet" style={documentStyle} ref={ref} id="print-area" aria-label="振假名成品页">
        {(meta.title.trim() || byline) && (
          <header className="documentHeader">
            {meta.title.trim() && <h3>{meta.title}</h3>}
            {byline && <p>{byline}</p>}
          </header>
        )}

        <div className={`documentLyrics ${layout.vertical ? "verticalLyrics" : ""}`}>
          {lines.map((line, lineIndex) => (
            <div className="lyricsLine" key={`${lineIndex}-${line.source}`}>
              {line.segments.length === 0 ? (
                <span>&nbsp;</span>
              ) : (
                line.segments.map((segment, segmentIndex) => {
                  const isSelected =
                    selected?.lineIndex === lineIndex && selected?.segmentIndex === segmentIndex;
                  const className = `segment ${segment.ruby ? "editable" : ""} ${isSelected ? "selected" : ""}`;

                  return segment.ruby ? (
                    <ruby
                      className={className}
                      key={`${lineIndex}-${segmentIndex}`}
                      onClick={() => onSelect(lineIndex, segmentIndex)}
                      title="点击修改读音"
                    >
                      {segment.text}
                      <rt>{segment.ruby}</rt>
                    </ruby>
                  ) : (
                    <span className={className} key={`${lineIndex}-${segmentIndex}`}>
                      {segment.text}
                    </span>
                  );
                })
              )}
            </div>
          ))}
        </div>
      </article>
    </div>
  );
});

export default RubyPreview;
