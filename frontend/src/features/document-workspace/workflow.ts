import type { DocumentItem, DocumentStatus } from "./types";

const byteUnits = ["B", "KB", "MB", "GB"] as const;

export function isSupportedPdf(file: File) {
  return (
    file.type === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf")
  );
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < byteUnits.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${Number.isInteger(value) ? value : value.toFixed(1)} ${byteUnits[unitIndex]}`;
}

export function createDocumentItems(
  files: File[],
  status: DocumentStatus
): DocumentItem[] {
  return files.map((file, index) => ({
    id: `${file.name}-${file.size}-${file.lastModified}-${index}`,
    name: file.name,
    size: file.size,
    status
  }));
}

export function fileCountLabel(count: number) {
  return count === 1 ? "1 PDF" : `${count} PDFs`;
}
