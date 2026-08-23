import { describe, expect, it } from "vitest";

import {
  calculateA4PdfLayout,
  calculatePdfPageSlices,
  calculateSafePdfBreakpoints,
} from "./pdf";

describe("PDF layout", () => {
  it("uses a stable A4 content width independent of the viewport", () => {
    const layout = calculateA4PdfLayout(56);
    expect(layout.pageMarginMm).toBeCloseTo(14.8167, 4);
    expect(layout.captureWidthPx).toBe(682);
  });

  it("only keeps breakpoints that do not cross another column", () => {
    expect(calculateSafePdfBreakpoints([
      { top: 0, bottom: 100 },
      { top: 100, bottom: 200 },
      { top: 0, bottom: 120 },
      { top: 120, bottom: 220 },
    ])).toEqual([220]);
    expect(calculateSafePdfBreakpoints([
      { top: 0, bottom: 100 },
      { top: 100, bottom: 200 },
      { top: 0, bottom: 100 },
      { top: 100, bottom: 200 },
    ])).toEqual([100, 200]);
  });
});

describe("PDF pagination", () => {
  it("keeps short documents on one page", () => {
    expect(calculatePdfPageSlices(900, 1200)).toEqual([{ startY: 0, height: 900 }]);
  });

  it("fills pages when there are no safe line boundaries", () => {
    expect(calculatePdfPageSlices(2500, 1000)).toEqual([
      { startY: 0, height: 1000 },
      { startY: 1000, height: 1000 },
      { startY: 2000, height: 500 },
    ]);
  });

  it("moves a page break to the closest safe line boundary", () => {
    expect(calculatePdfPageSlices(2100, 1000, [480, 940, 1450, 1880])).toEqual([
      { startY: 0, height: 940 },
      { startY: 940, height: 940 },
      { startY: 1880, height: 220 },
    ]);
  });

  it("does not create a mostly empty page for an early breakpoint", () => {
    expect(calculatePdfPageSlices(1500, 1000, [200])).toEqual([
      { startY: 0, height: 1000 },
      { startY: 1000, height: 500 },
    ]);
  });
});
