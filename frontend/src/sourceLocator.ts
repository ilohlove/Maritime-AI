// Location types are future-compatible contracts, not supported import formats.
export type SourceLocator =
  | { kind: "page"; page_number: number }
  | { kind: "section"; heading: string; paragraph?: number | null }
  | { kind: "sheet"; sheet_name: string; cell_range: string }
  | { kind: "rows"; start: number; end: number }
  | { kind: "lines"; start: number; end: number }
  | { kind: "image"; bbox?: [number, number, number, number] | null };

export function sourceLabel(locator: SourceLocator): string {
  switch (locator.kind) {
    case "page": return `Page ${locator.page_number}`;
    case "section": return `Section ${locator.heading}${locator.paragraph ? ` · Paragraph ${locator.paragraph}` : ""}`;
    case "sheet": return `Sheet ${locator.sheet_name} · ${locator.cell_range}`;
    case "rows": return `Rows ${locator.start}–${locator.end}`;
    case "lines": return `Lines ${locator.start}–${locator.end}`;
    case "image": return locator.bbox ? `Image · Region ${locator.bbox.join(", ")}` : "Image";
  }
}
