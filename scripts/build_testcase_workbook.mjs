import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const projectRoot = process.cwd();
const sourcePath = path.join(projectRoot, "BANG_TESTCASE_THEO_CHUC_NANG.md");
const outputDir = path.join(projectRoot, "outputs", "testcase_workbook");
const outputPath = path.join(outputDir, "BANG_TESTCASE_THEO_CHUC_NANG.xlsx");
const rootOutputPath = path.join(projectRoot, "BANG_TESTCASE_THEO_CHUC_NANG.xlsx");

function splitMarkdownRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim().replace(/`/g, "").replace(/\*\*/g, ""));
}

function isSeparatorRow(line) {
  return /^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line.trim());
}

function parseMarkdownTables(markdown) {
  const lines = markdown.split(/\r?\n/);
  const sections = [];
  let currentSection = "Tổng hợp";

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].trim();
    const heading = line.match(/^##\s+(.*)$/);
    if (heading) {
      currentSection = heading[1].replace(/^\d+\.\s*/, "").trim();
      continue;
    }

    if (!line.startsWith("|") || i + 1 >= lines.length || !isSeparatorRow(lines[i + 1])) {
      continue;
    }

    const headers = splitMarkdownRow(line);
    const rows = [];
    i += 2;
    while (i < lines.length && lines[i].trim().startsWith("|")) {
      rows.push(splitMarkdownRow(lines[i]));
      i += 1;
    }
    i -= 1;

    sections.push({ section: currentSection, headers, rows });
  }

  return sections;
}

function sheetNameFor(section) {
  if (section.includes("Tìm Kiếm")) return "Search";
  if (section.includes("Lọc")) return "Filter";
  if (section.includes("Sắp Xếp")) return "Sort";
  if (section.includes("Tổng Hợp")) return "Tong hop";
  return section.slice(0, 31);
}

function writeTitle(sheet, title, subtitle, colCount) {
  const titleRange = sheet.getRangeByIndexes(0, 0, 1, colCount);
  titleRange.merge();
  titleRange.values = [[title]];
  titleRange.format = {
    fill: "#1D4ED8",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  titleRange.format.rowHeightPx = 34;

  const subtitleRange = sheet.getRangeByIndexes(1, 0, 1, colCount);
  subtitleRange.merge();
  subtitleRange.values = [[subtitle]];
  subtitleRange.format = {
    fill: "#EFF6FF",
    font: { italic: true, color: "#1E3A8A" },
    horizontalAlignment: "left",
    verticalAlignment: "center",
    wrapText: true,
  };
  subtitleRange.format.rowHeightPx = 28;
}

function setColumnWidths(sheet, headers) {
  const widths = {
    "Mã TC": 110,
    "Tên Test Case": 230,
    "Mục tiêu": 280,
    "Dữ liệu đầu vào (Input)": 210,
    "Các bước thực hiện": 320,
    "Kết quả mong đợi": 320,
    "Mức độ": 90,
    "Phân hệ (Module)": 260,
    "Tổng số TC": 110,
  };

  headers.forEach((header, idx) => {
    const width = widths[header] || 160;
    sheet.getRangeByIndexes(0, idx, 200, 1).format.columnWidthPx = width;
  });
}

function styleTable(sheet, headers, rows, startRow) {
  const rowCount = rows.length + 1;
  const colCount = headers.length;
  const tableRange = sheet.getRangeByIndexes(startRow, 0, rowCount, colCount);
  tableRange.format = {
    borders: { preset: "all", style: "thin", color: "#9CA3AF" },
    verticalAlignment: "top",
    wrapText: true,
  };

  const headerRange = sheet.getRangeByIndexes(startRow, 0, 1, colCount);
  headerRange.format = {
    fill: "#DBEAFE",
    font: { bold: true, color: "#111827" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#6B7280" },
  };
  headerRange.format.rowHeightPx = 42;

  if (rows.length) {
    const bodyRange = sheet.getRangeByIndexes(startRow + 1, 0, rows.length, colCount);
    bodyRange.format = {
      verticalAlignment: "top",
      wrapText: true,
      borders: { preset: "all", style: "thin", color: "#D1D5DB" },
    };
    bodyRange.format.rowHeightPx = 78;

    const severityCol = headers.indexOf("Mức độ");
    if (severityCol >= 0) {
      for (let r = 0; r < rows.length; r += 1) {
        const value = String(rows[r][severityCol] || "").toLowerCase();
        const cell = sheet.getCell(startRow + 1 + r, severityCol);
        if (value.includes("critical")) {
          cell.format = { fill: "#FEE2E2", font: { bold: true, color: "#991B1B" }, horizontalAlignment: "center" };
        } else if (value.includes("high")) {
          cell.format = { fill: "#FFEDD5", font: { bold: true, color: "#9A3412" }, horizontalAlignment: "center" };
        } else if (value.includes("medium")) {
          cell.format = { fill: "#FEF9C3", font: { bold: true, color: "#854D0E" }, horizontalAlignment: "center" };
        } else if (value.includes("low")) {
          cell.format = { fill: "#DCFCE7", font: { bold: true, color: "#166534" }, horizontalAlignment: "center" };
        }
      }
    }
  }
}

function addWorksheet(workbook, table, subtitle) {
  const name = sheetNameFor(table.section);
  const sheet = workbook.worksheets.add(name);
  const colCount = table.headers.length;
  sheet.showGridLines = false;
  writeTitle(sheet, table.section, subtitle, colCount);
  sheet.getRangeByIndexes(3, 0, 1, colCount).values = [table.headers];
  if (table.rows.length) {
    sheet.getRangeByIndexes(4, 0, table.rows.length, colCount).values = table.rows;
  }
  styleTable(sheet, table.headers, table.rows, 3);
  setColumnWidths(sheet, table.headers);
  try {
    sheet.freezePanes.freezeRows(4);
  } catch {
    // Freeze panes are cosmetic; export should continue if unavailable.
  }
  return sheet;
}

const markdown = await fs.readFile(sourcePath, "utf8");
const tables = parseMarkdownTables(markdown);
const workbook = Workbook.create();

const summaryTable = tables.find((table) => table.section.includes("Tổng Hợp"));
const featureTables = tables.filter((table) => !table.section.includes("Tổng Hợp"));

const summarySheet = workbook.worksheets.add("Tong hop");
summarySheet.showGridLines = false;
writeTitle(
  summarySheet,
  "Bảng Test Case Theo Chức Năng",
  "Nguồn: BANG_TESTCASE_THEO_CHUC_NANG.md - phạm vi 3 chức năng Search, Filter, Sort.",
  5,
);
summarySheet.getRange("A4:B4").values = [["Chỉ tiêu", "Giá trị"]];
summarySheet.getRange("A5:B8").values = [
  ["Tổng số test case", featureTables.reduce((sum, table) => sum + table.rows.length, 0)],
  ["Tìm kiếm (Search)", featureTables.find((table) => table.section.includes("Tìm Kiếm"))?.rows.length || 0],
  ["Lọc (Filter)", featureTables.find((table) => table.section.includes("Lọc"))?.rows.length || 0],
  ["Sắp xếp (Sort)", featureTables.find((table) => table.section.includes("Sắp Xếp"))?.rows.length || 0],
];
styleTable(summarySheet, ["Chỉ tiêu", "Giá trị"], summarySheet.getRange("A5:B8").values, 3);
summarySheet.getRange("A:A").format.columnWidthPx = 260;
summarySheet.getRange("B:B").format.columnWidthPx = 120;

if (summaryTable) {
  const startRow = 10;
  summarySheet.getRangeByIndexes(startRow, 0, 1, summaryTable.headers.length).values = [summaryTable.headers];
  summarySheet.getRangeByIndexes(startRow + 1, 0, summaryTable.rows.length, summaryTable.headers.length).values = summaryTable.rows;
  styleTable(summarySheet, summaryTable.headers, summaryTable.rows, startRow);
}

for (const table of featureTables) {
  addWorksheet(workbook, table, "Bảng testcase chi tiết theo chức năng.");
}

await fs.mkdir(outputDir, { recursive: true });

for (const sheetName of ["Tong hop", ...featureTables.map((table) => sheetNameFor(table.section))]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(
    path.join(outputDir, `${sheetName.replace(/\s+/g, "_").toLowerCase()}_preview.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
});
console.log(errors.ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
let savedPath = outputPath;
try {
  await xlsx.save(outputPath);
} catch (error) {
  if (error && error.code === "EBUSY") {
    savedPath = path.join(outputDir, "BANG_TESTCASE_THEO_CHUC_NANG_fixed.xlsx");
    await xlsx.save(savedPath);
  } else {
    throw error;
  }
}

try {
  await xlsx.save(rootOutputPath);
} catch (error) {
  if (!error || error.code !== "EBUSY") {
    throw error;
  }
}

console.log(savedPath);
