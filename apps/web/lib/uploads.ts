// The vault's accepted file types, shared by every surface that uploads into
// it (the vault itself, the chat composer). Mirrors the API's ALLOWED_MIMES.

export const EXT_MIMES: Record<string, string> = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  txt: "text/plain",
  md: "text/markdown",
  csv: "text/csv",
};

export const ACCEPT =
  ".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv," + Object.values(EXT_MIMES).join(",");

/** The upload's mime, from the browser or the extension; null = unsupported. */
export function uploadMime(file: File): string | null {
  const mime = file.type || EXT_MIMES[file.name.split(".").pop()?.toLowerCase() ?? ""];
  return mime && Object.values(EXT_MIMES).includes(mime) ? mime : null;
}
