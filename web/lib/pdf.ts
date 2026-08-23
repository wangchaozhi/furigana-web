const A4_WIDTH_MM = 210;
const A4_HEIGHT_MM = 297;
const MIN_PAGE_FILL_RATIO = 0.55;
const CSS_PIXELS_PER_INCH = 96;
const MILLIMETERS_PER_INCH = 25.4;
const MIN_PAGE_MARGIN_MM = 5;
const MAX_PAGE_MARGIN_MM = 30;

export type PdfPageSlice = {
  startY: number;
  height: number;
};

export type CanvasPdfOptions = {
  title: string;
  pageMarginMm: number;
  breakpoints?: number[];
};

export type PdfContentRange = {
  top: number;
  bottom: number;
};

export function calculateA4PdfLayout(pageMarginPx: number) {
  const requestedMarginMm = pageMarginPx * MILLIMETERS_PER_INCH / CSS_PIXELS_PER_INCH;
  const pageMarginMm = Math.min(MAX_PAGE_MARGIN_MM, Math.max(MIN_PAGE_MARGIN_MM, requestedMarginMm));
  const captureWidthPx = Math.round(
    (A4_WIDTH_MM - pageMarginMm * 2) * CSS_PIXELS_PER_INCH / MILLIMETERS_PER_INCH,
  );
  return { pageMarginMm, captureWidthPx };
}

export function calculateSafePdfBreakpoints(ranges: PdfContentRange[]): number[] {
  const normalizedRanges = ranges
    .map(({ top, bottom }) => ({ top: Math.min(top, bottom), bottom: Math.max(top, bottom) }))
    .filter(({ top, bottom }) => Number.isFinite(top) && Number.isFinite(bottom) && bottom > top);
  const candidates = Array.from(new Set(normalizedRanges.map(({ bottom }) => bottom)))
    .sort((a, b) => a - b);

  return candidates.filter((candidate) => !normalizedRanges.some(
    ({ top, bottom }) => top < candidate && candidate < bottom,
  ));
}

export function calculatePdfPageSlices(
  totalHeight: number,
  maxPageHeight: number,
  breakpoints: number[] = [],
): PdfPageSlice[] {
  const normalizedTotal = Math.max(0, Math.round(totalHeight));
  const normalizedPageHeight = Math.max(1, Math.floor(maxPageHeight));
  if (!normalizedTotal) return [];

  const usableBreakpoints = Array.from(new Set(
    breakpoints
      .map((value) => Math.round(value))
      .filter((value) => value > 0 && value < normalizedTotal),
  )).sort((a, b) => a - b);

  const slices: PdfPageSlice[] = [];
  let startY = 0;
  while (startY < normalizedTotal) {
    const remaining = normalizedTotal - startY;
    if (remaining <= normalizedPageHeight) {
      slices.push({ startY, height: remaining });
      break;
    }

    const targetEnd = startY + normalizedPageHeight;
    const minimumPreferredEnd = startY + Math.floor(normalizedPageHeight * MIN_PAGE_FILL_RATIO);
    const preferredEnd = usableBreakpoints
      .filter((value) => value >= minimumPreferredEnd && value <= targetEnd)
      .at(-1);
    const endY = preferredEnd ?? targetEnd;
    slices.push({ startY, height: endY - startY });
    startY = endY;
  }

  return slices;
}

export async function createA4PdfFromCanvas(
  canvas: HTMLCanvasElement,
  { title, pageMarginMm, breakpoints = [] }: CanvasPdfOptions,
): Promise<Blob> {
  if (!canvas.width || !canvas.height) throw new Error("PDF 画布为空");

  const marginMm = Math.min(MAX_PAGE_MARGIN_MM, Math.max(MIN_PAGE_MARGIN_MM, pageMarginMm));
  const contentWidthMm = A4_WIDTH_MM - marginMm * 2;
  const contentHeightMm = A4_HEIGHT_MM - marginMm * 2;
  const maxPageHeightPx = Math.floor(canvas.width * contentHeightMm / contentWidthMm);
  const slices = calculatePdfPageSlices(canvas.height, maxPageHeightPx, breakpoints);
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
    compress: true,
    putOnlyUsedFonts: true,
  });
  pdf.setProperties({
    title,
    subject: "Furigana Studio export",
    creator: "Furigana Studio",
  });

  slices.forEach((slice, pageIndex) => {
    if (pageIndex > 0) pdf.addPage("a4", "portrait");
    const pageCanvas = canvas.ownerDocument.createElement("canvas");
    try {
      pageCanvas.width = canvas.width;
      pageCanvas.height = slice.height;
      const context = pageCanvas.getContext("2d");
      if (!context) throw new Error("浏览器无法创建 PDF 画布");
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, pageCanvas.width, pageCanvas.height);
      context.drawImage(
        canvas,
        0,
        slice.startY,
        canvas.width,
        slice.height,
        0,
        0,
        canvas.width,
        slice.height,
      );
      const renderedHeightMm = slice.height * contentWidthMm / canvas.width;
      pdf.addImage(
        pageCanvas.toDataURL("image/png"),
        "PNG",
        marginMm,
        marginMm,
        contentWidthMm,
        renderedHeightMm,
        undefined,
        "FAST",
      );
    } finally {
      pageCanvas.width = 0;
      pageCanvas.height = 0;
    }
  });

  return pdf.output("blob");
}
