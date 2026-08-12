"use client";

import { forwardRef } from "react";
import type { AnnotatedLine, DocumentMeta } from "@/lib/types";

type Selection = { lineIndex: number; segmentIndex: number } | null;

type Props = {
  meta: DocumentMeta;
  lines: AnnotatedLine[];
  selected: Selection;
  onSelect: (lineIndex: number, segmentIndex: number) => void;
};

const RubyPreview = forwardRef<HTMLElement, Props>(function RubyPreview(
  { meta, lines, selected, onSelect },
  ref,
) {
  if (!lines.length) {
    return <div className="emptyState">标注后会在这里预览。只给汉字显示振假名。</div>;
  }

  const byline = [meta.artist.trim() ? `Song by ${meta.artist.trim()}` : "", meta.year.trim()]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="previewScroll">
      <article className="documentSheet" ref={ref} id="print-area" aria-label="振假名成品页">
        {(meta.title.trim() || byline) && (
          <header className="documentHeader">
            {meta.title.trim() && <h3>{meta.title}</h3>}
            {byline && <p>{byline}</p>}
          </header>
        )}

        <div className="documentLyrics">
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
