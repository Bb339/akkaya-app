import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "file:///C:/Users/LENOVO/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const outDir = path.resolve("docs/data_templates");
const previewDir = path.resolve(".template-previews");
await fs.mkdir(outDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const commonHeaders = ["planning_year", "observation_year", "authority_class", "source_institution", "source_reference", "currency", "geographic_scope", "crop_scope", "measurement_method", "notes"];
const commonValues = [2024, 2024, "DERIVED_PROXY", "SYNTHETIC", "not_official", "TRY", "project", "catalog", "synthetic_example", "SYNTHETIC example; replace with sourced values"];
const templates = [
  ["crop_yield_template.xlsx", ["crop", "yield_value", "yield_unit", ...commonHeaders], ["TURP", 2500, "kg/da", ...commonValues]],
  ["crop_sale_price_template.xlsx", ["crop", "price", "price_unit", "price_period", ...commonHeaders], ["TURP", 6, "TL/kg", "2024 average", ...commonValues]],
  ["crop_support_template.xlsx", ["crop", "support_type", "amount", "unit", ...commonHeaders], ["TURP", "synthetic_support", 100, "TL/da", ...commonValues]],
  ["crop_cost_components_template.xlsx", ["crop", "cost_category", "amount", "unit", ...commonHeaders], ["TURP", "seed", 1000, "TL/da", ...commonValues]],
  ["crop_net_profit_template.xlsx", ["crop", "net_profit_per_da", "calculation_method", "dependency_dataset_ids", ...commonHeaders], ["TURP", 4000, "DIRECT_SOURCE", "", ...commonValues]],
  ["analysis_unit_economics_template.xlsx", ["analysis_unit_id", "crop", "gross_revenue", "total_cost", "net_profit", ...commonHeaders], ["P1", "TURP", 150000, 110000, 40000, ...commonValues]],
  ["seasonal_economics_template.xlsx", ["analysis_unit_id", "crop", "season", "yield_value", "yield_unit", "price", "price_unit", "cost", "cost_unit", "net_profit", "net_profit_unit", ...commonHeaders], ["", "TURP", "SECONDARY", 2.5, "ton/da", 15000, "TL/ton", 11000, "TL/da", 4000, "TL/da", ...commonValues]],
];

for (const [filename, headers, values] of templates) {
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add("Data");
  sheet.showGridLines = false;
  sheet.getRangeByIndexes(0, 0, 2, headers.length).values = [headers, values];
  const used = sheet.getRangeByIndexes(0, 0, 2, headers.length);
  used.format.font = { name: "Arial", size: 10, color: "#1F2937" };
  used.format.verticalAlignment = "center";
  const header = sheet.getRangeByIndexes(0, 0, 1, headers.length);
  header.format = { fill: "#374151", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: false,
                    borders: { preset: "inside", style: "thin", color: "#FFFFFF" } };
  header.format.rowHeight = 24;
  const body = sheet.getRangeByIndexes(1, 0, 1, headers.length);
  body.format.fill = "#FFF7D6";
  body.format.rowHeight = 22;
  used.format.autofitColumns();
  for (let col = 0; col < headers.length; col++) {
    const range = sheet.getRangeByIndexes(0, col, 2, 1);
    if (range.format.columnWidth > 28) range.format.columnWidth = 28;
    if (range.format.columnWidth < 11) range.format.columnWidth = 11;
  }
  sheet.freezePanes.freezeRows(1);
  workbook.recalculate();
  const formulaInspection = await workbook.inspect({ kind: "formula", sheetId: "Data", range: `A1:${String.fromCharCode(64 + Math.min(headers.length, 26))}2`, maxChars: 2000, options: { maxResults: 50 } });
  const formulaText = JSON.stringify(formulaInspection);
  if (formulaText.includes("#REF!") || formulaText.includes("#VALUE!") || formulaText.includes("#DIV/0!")) throw new Error(`Formula error in ${filename}`);
  const region = await workbook.inspect({ kind: "region", sheetId: "Data", range: `A1:${String.fromCharCode(64 + Math.min(headers.length, 26))}2`, maxChars: 4000 });
  const verifiedValues = sheet.getRangeByIndexes(0, 0, 2, headers.length).values.flat().map(String);
  if (!verifiedValues.includes("SYNTHETIC") || !verifiedValues.includes("not_official")) throw new Error(`Synthetic labels missing from ${filename}`);
  const preview = await workbook.render({ sheetName: "Data", autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, filename.replace(".xlsx", ".png")), new Uint8Array(await preview.arrayBuffer()));
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(path.join(outDir, filename));
}

console.log(JSON.stringify({ created: templates.map(([name]) => name), previewDir }));
