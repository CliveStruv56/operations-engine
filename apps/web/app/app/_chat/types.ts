/** Shapes the chat panel's parts share. Local to the chat UI — the API's
 *  message payload is narrower than lib/ types and only read here. */

export type Citation = {
  n: number;
  chunk_id: string;
  document_id: string;
  title: string;
  page_start: number | null;
  page_end: number | null;
  snippet: string;
  url?: string | null;
  source_type?: string;
};

export type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[];
  model: string | null;
  cost_usd: number | null;
};
