import { sourceLabel, type SourceLocator } from "./sourceLocator";

it.each<[SourceLocator, string]>([
  [{kind:"page",page_number:2}, "Page 2"],
  [{kind:"section",heading:"Safety",paragraph:3}, "Section Safety · Paragraph 3"],
  [{kind:"sheet",sheet_name:"Safety",cell_range:"B2:D4"}, "Sheet Safety · B2:D4"],
  [{kind:"rows",start:2,end:4}, "Rows 2–4"],
  [{kind:"lines",start:3,end:9}, "Lines 3–9"],
  [{kind:"image"}, "Image"],
])("renders the typed locator without inventing page numbers", (locator, expected) => {
  expect(sourceLabel(locator)).toBe(expected);
});
