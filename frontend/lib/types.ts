export type ComponentHealth = {
  status: "ok" | "error" | string;
  detail?: string | null;
};

export type ReadinessResponse = {
  status: "ok" | "degraded" | string;
  components: Record<string, ComponentHealth>;
};

export type DashboardStats = {
  connectors: number;
  active_documents: number;
  deleted_documents: number;
  chunks: number;
  sync_runs: number;
  last_sync_status: string | null;
};

export type Connector = {
  id: string;
  tenant_id: string;
  name: string;
  type: "local" | "sharepoint" | "google_drive" | string;
  status: string;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type SyncRun = {
  id: string;
  tenant_id: string;
  connector_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  files_seen: number;
  files_indexed: number;
  files_deleted: number;
  error_message: string | null;
  stats: Record<string, unknown>;
};

export type DocumentItem = {
  id: string;
  tenant_id: string;
  connector_id: string;
  external_id: string;
  title: string;
  path: string;
  source_url: string | null;
  mime_type: string | null;
  checksum: string | null;
  version: string | null;
  size_bytes: number | null;
  source_modified_at: string | null;
  deleted_at: string | null;
};

export type SourceCitation = {
  source_id: string;
  document_id: string;
  title: string;
  path: string;
  source_url: string | null;
  page: number | null;
  score: number | null;
};

export type ChatResponse = {
  answer: string;
  citations: SourceCitation[];
  conversation_id: string;
};

export type Conversation = {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: SourceCitation[];
  created_at: string;
};
