"use client";

import {
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  FileText,
  FolderOpen,
  Loader2,
  LogOut,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  Upload,
  XCircle
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Connector, Conversation, SourceCitation } from "@/lib/types";

type View = "chat" | "sources";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: SourceCitation[];
};


export default function Home() {
  const [view, setView] = useState<View>("chat");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [systemOk, setSystemOk] = useState<boolean | null>(null);
  const [currentUser, setCurrentUser] = useState<{ email: string | null; display_name: string | null } | null>(null);

  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [docCount, setDocCount] = useState(0);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  const [connectorName, setConnectorName] = useState("Mes documents");
  const [connectorType, setConnectorType] = useState<"local" | "google_drive" | "sharepoint" | "notion">("local");
  const [notionToken, setNotionToken] = useState("");
  const [notionDatabaseId, setNotionDatabaseId] = useState("");
  const [notionPageId, setNotionPageId] = useState("");
  const [rootPath, setRootPath] = useState(
    process.env.NEXT_PUBLIC_DEFAULT_LOCAL_ROOT ?? "./sample_docs"
  );
  const [gdServiceAccount, setGdServiceAccount] = useState("");
  const [gdFolderId, setGdFolderId] = useState("");
  const [spTenantId, setSpTenantId] = useState("");
  const [spClientId, setSpClientId] = useState("");
  const [spClientSecret, setSpClientSecret] = useState("");
  const [spSiteId, setSpSiteId] = useState("");
  const [spDriveId, setSpDriveId] = useState("");
  const [sourcesBusy, setSourcesBusy] = useState(false);
  const [sourcesMsg, setSourcesMsg] = useState("");
  const [uploadDragging, setUploadDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const loadStatus = useCallback(async () => {
    const [readiness, stats, nextConnectors, nextConversations] = await Promise.allSettled([
      api.readiness(),
      api.stats(),
      api.connectors(),
      api.conversations()
    ]);
    setSystemOk(readiness.status === "fulfilled" && readiness.value.status === "ok");
    if (stats.status === "fulfilled") setDocCount(stats.value.active_documents);
    if (nextConnectors.status === "fulfilled") setConnectors(nextConnectors.value);
    if (nextConversations.status === "fulfilled") setConversations(nextConversations.value);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("docmind_token");
    if (!token) {
      window.location.href = "/login";
      return;
    }
    const stored = localStorage.getItem("docmind_user");
    if (stored) {
      try {
        setCurrentUser(JSON.parse(stored) as { email: string | null; display_name: string | null });
      } catch {}
    }
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function loadConversation(conv: Conversation) {
    setLoading(true);
    try {
      const msgs = await api.conversationMessages(conv.id);
      setMessages(
        msgs.map((m) => ({ id: m.id, role: m.role, content: m.content, citations: m.citations }))
      );
      setActiveConversationId(conv.id);
      setView("chat");
    } catch {
      // silently ignore
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await api.chat(trimmed, 8, activeConversationId ?? undefined);
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer,
        citations: response.citations.filter((c) => c.title)
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setActiveConversationId(response.conversation_id);
      setDocCount((prev) => Math.max(prev, response.citations.length));
      const updated = await api.conversations();
      setConversations(updated);
    } catch (error) {
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          error instanceof Error
            ? `Une erreur est survenue : ${error.message}`
            : "Une erreur inattendue est survenue. Veuillez réessayer."
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();
    void sendMessage(input);
  }

  function handleKeyDown(event: { key: string; shiftKey: boolean; preventDefault(): void }) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(input);
    }
  }

  async function syncConnector(connectorId: string) {
    setSourcesBusy(true);
    setSourcesMsg("Indexation en cours…");
    try {
      const syncRun = await api.syncConnector(connectorId);
      // Interroge le statut toutes les 3 secondes jusqu'à la fin
      let attempts = 0;
      const poll = async (): Promise<void> => {
        attempts++;
        if (attempts > 60) {
          setSourcesMsg("Indexation en cours en arrière-plan.");
          setSourcesBusy(false);
          return;
        }
        try {
          const runs = await api.syncRuns(connectorId);
          const current = runs.find((r) => r.id === syncRun.id);
          if (current?.status === "succeeded") {
            await loadStatus();
            setSourcesMsg("Documents indexés avec succès.");
            setSourcesBusy(false);
          } else if (current?.status === "failed") {
            await loadStatus();
            setSourcesMsg(`Échec de l'indexation : ${current.error_message ?? "erreur inconnue"}`);
            setSourcesBusy(false);
          } else {
            setTimeout(() => void poll(), 3000);
          }
        } catch {
          setTimeout(() => void poll(), 3000);
        }
      };
      setTimeout(() => void poll(), 3000);
    } catch (error) {
      await loadStatus();
      const msg = error instanceof Error ? error.message : "Mise à jour impossible.";
      setSourcesMsg(`Échec de l'indexation : ${msg}`);
      setSourcesBusy(false);
    }
  }

  async function deleteConnector(connectorId: string) {
    setSourcesBusy(true);
    setSourcesMsg("");
    try {
      await api.deleteConnector(connectorId);
      await loadStatus();
      setSourcesMsg("Source supprimée.");
    } catch (error) {
      setSourcesMsg(error instanceof Error ? error.message : "Suppression impossible.");
    } finally {
      setSourcesBusy(false);
    }
  }

  function logout() {
    localStorage.removeItem("docmind_token");
    localStorage.removeItem("docmind_user");
    window.location.href = "/login";
  }

  async function handleFileUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    const allowed = [".pdf", ".docx", ".txt"];
    for (const file of Array.from(files)) {
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!allowed.includes(ext)) {
        setSourcesMsg(`Format non supporté : ${file.name}. Formats acceptés : PDF, DOCX, TXT.`);
        return;
      }
    }
    setSourcesBusy(true);
    setSourcesMsg("");
    let uploaded = 0;
    for (const file of Array.from(files)) {
      setUploadProgress(`Envoi de ${file.name}…`);
      try {
        await api.uploadDocument(file);
        uploaded++;
      } catch (error) {
        setSourcesMsg(error instanceof Error ? error.message : "Upload impossible.");
        setUploadProgress(null);
        setSourcesBusy(false);
        return;
      }
    }
    setUploadProgress(null);
    await loadStatus();
    setSourcesMsg(`${uploaded} fichier${uploaded > 1 ? "s" : ""} importé${uploaded > 1 ? "s" : ""} et indexé${uploaded > 1 ? "s" : ""} avec succès.`);
    setSourcesBusy(false);
  }

  async function createConnector(event: { preventDefault(): void }) {
    event.preventDefault();
    setSourcesBusy(true);
    setSourcesMsg("");
    try {
      let config: Record<string, unknown>;
      if (connectorType === "local") {
        config = { root_path: rootPath.trim() };
      } else if (connectorType === "google_drive") {
        let saInfo: unknown;
        try {
          saInfo = JSON.parse(gdServiceAccount);
        } catch {
          setSourcesMsg("Le JSON du compte de service est invalide.");
          return;
        }
        config = {
          service_account_info: saInfo,
          ...(gdFolderId.trim() && { folder_id: gdFolderId.trim() }),
        };
      } else if (connectorType === "notion") {
        config = {
          notion_token: notionToken.trim(),
          ...(notionDatabaseId.trim() && { database_id: notionDatabaseId.trim() }),
          ...(notionPageId.trim() && { page_id: notionPageId.trim() }),
        };
      } else {
        config = {
          tenant_id: spTenantId.trim(),
          client_id: spClientId.trim(),
          client_secret: spClientSecret.trim(),
          ...(spSiteId.trim() && { site_id: spSiteId.trim() }),
          ...(spDriveId.trim() && { drive_id: spDriveId.trim() }),
        };
      }
      await api.createConnector(connectorName.trim(), connectorType, config);
      await loadStatus();
      setConnectorName("Mes documents");
      setRootPath(process.env.NEXT_PUBLIC_DEFAULT_LOCAL_ROOT ?? "./sample_docs");
      setGdServiceAccount("");
      setGdFolderId("");
      setSpTenantId("");
      setSpClientId("");
      setSpClientSecret("");
      setSpSiteId("");
      setSpDriveId("");
      setNotionToken("");
      setNotionDatabaseId("");
      setNotionPageId("");
      setSourcesMsg("Source connectée. Cliquez sur Mettre à jour pour indexer les documents.");
    } catch (error) {
      setSourcesMsg(error instanceof Error ? error.message : "Connexion impossible.");
    } finally {
      setSourcesBusy(false);
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Sparkles size={18} />
          </div>
          <div className="brand-text">
            <strong>DocMind</strong>
            <span>Deep Bleue IA</span>
          </div>
        </div>

        <button
          className="new-chat-btn"
          type="button"
          onClick={() => {
            setMessages([]);
            setActiveConversationId(null);
            setView("chat");
            textareaRef.current?.focus();
          }}
        >
          <Plus size={16} />
          Nouvelle conversation
        </button>

        <nav className="sidebar-nav">
          <button
            className={`nav-item ${view === "chat" ? "active" : ""}`}
            type="button"
            onClick={() => setView("chat")}
          >
            <MessageSquare size={16} />
            Assistant
          </button>
          <button
            className={`nav-item ${view === "sources" ? "active" : ""}`}
            type="button"
            onClick={() => setView("sources")}
          >
            <BookOpen size={16} />
            Sources
            {docCount > 0 && <span className="nav-badge">{docCount}</span>}
          </button>
        </nav>

        {conversations.length > 0 && (
          <div className="conversations-list">
            <div className="conversations-label">Récents</div>
            {conversations.slice(0, 15).map((conv) => (
              <div
                key={conv.id}
                className={`conversation-item ${activeConversationId === conv.id ? "active" : ""}`}
              >
                <button
                  className="conv-main"
                  type="button"
                  onClick={() => void loadConversation(conv)}
                >
                  <MessageSquare size={13} />
                  <span>{conv.title ?? "Conversation"}</span>
                </button>
                <button
                  className="conv-delete"
                  type="button"
                  title="Supprimer"
                  onClick={async (e) => {
                    e.stopPropagation();
                    try {
                      await api.deleteConversation(conv.id);
                      if (activeConversationId === conv.id) {
                        setMessages([]);
                        setActiveConversationId(null);
                      }
                      setConversations((prev) => prev.filter((c) => c.id !== conv.id));
                    } catch { /* silently ignore */ }
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="sidebar-footer">
          <div className={`system-status ${systemOk === null ? "loading" : systemOk ? "ok" : "error"}`}>
            <span className="status-dot" />
            {systemOk === null ? "Connexion…" : systemOk ? "Système opérationnel" : "Système indisponible"}
          </div>
        </div>

        {currentUser && (
          <div className="sidebar-user">
            <div className="user-avatar">
              {(currentUser.display_name ?? currentUser.email ?? "U")[0].toUpperCase()}
            </div>
            <div className="user-info">
              <strong>{currentUser.display_name ?? currentUser.email}</strong>
              {currentUser.display_name && <span>{currentUser.email}</span>}
            </div>
            <button className="logout-btn" type="button" onClick={logout} title="Se déconnecter">
              <LogOut size={15} />
            </button>
          </div>
        )}
      </aside>

      <main className="main">
        {view === "chat" ? (
          <div className="chat-view">
            <div className="messages-area">
              {messages.length === 0 ? (
                <div className="welcome">
                  <div className="welcome-icon">
                    <Sparkles size={32} />
                  </div>
                  <h1>Comment puis-je vous aider ?</h1>
                  <p>
                    Posez une question sur vos documents. Je consulte uniquement les sources
                    autorisées et cite mes références.
                  </p>
                  {docCount === 0 && (
                    <div className="welcome-hint">
                      <FileText size={15} />
                      Aucun document indexé.{" "}
                      <button type="button" onClick={() => setView("sources")}>
                        Connectez une source
                        <ChevronRight size={13} />
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="message-list">
                  {messages.map((msg) => (
                    <div key={msg.id} className={`message-row ${msg.role}`}>
                      {msg.role === "assistant" && (
                        <div className="avatar">
                          <Sparkles size={15} />
                        </div>
                      )}
                      <div className="bubble-wrap">
                        <div className="bubble">{msg.content}</div>
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="citations">
                            {msg.citations.map((c) => (
                              <a
                                key={`${c.source_id}-${c.document_id}`}
                                className="citation-chip"
                                href={c.source_url ?? "#"}
                                target="_blank"
                                rel="noreferrer"
                                title={c.path}
                              >
                                <FileText size={12} />
                                {c.title}
                                {c.page ? ` · p.${c.page}` : ""}
                                {c.source_url && c.source_url !== "#" && (
                                  <ArrowUpRight size={11} />
                                )}
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                  {loading && (
                    <div className="message-row assistant">
                      <div className="avatar">
                        <Sparkles size={15} />
                      </div>
                      <div className="bubble-wrap">
                        <div className="bubble thinking">
                          <span /><span /><span />
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>

            <div className="input-bar">
              <form className="input-form" onSubmit={handleSubmit}>
                <textarea
                  ref={textareaRef}
                  className="chat-input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Posez votre question… (Entrée pour envoyer, Maj+Entrée pour sauter une ligne)"
                  rows={1}
                  disabled={loading}
                />
                <button
                  className="send-btn"
                  type="submit"
                  disabled={loading || !input.trim()}
                  aria-label="Envoyer"
                >
                  {loading ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
                </button>
              </form>
            </div>
          </div>
        ) : (
          <div className="sources-view">
            <header className="sources-header">
              <div>
                <h1>Sources documentaires</h1>
                <p>Connectez vos dossiers de documents pour les rendre accessibles à l&apos;assistant.</p>
              </div>
            </header>

            {sourcesMsg && (
              <div className={`sources-notice ${sourcesMsg.includes("impossible") || sourcesMsg.includes("erreur") ? "error" : ""}`}>
                {sourcesMsg.includes("impossible") || sourcesMsg.includes("erreur") ? (
                  <XCircle size={15} />
                ) : (
                  <CheckCircle2 size={15} />
                )}
                {sourcesMsg}
              </div>
            )}

            <section className="sources-section">
              <h2>Sources connectées</h2>
              {connectors.length === 0 ? (
                <div className="empty-sources">
                  <FolderOpen size={36} />
                  <p>Aucune source connectée.</p>
                  <span>Ajoutez un dossier de documents ci-dessous pour commencer.</span>
                </div>
              ) : (
                <div className="sources-list">
                  {connectors.map((connector) => (
                    <div className="source-card" key={connector.id}>
                      <div className="source-info">
                        <FolderOpen size={18} />
                        <div>
                          <strong>{connector.name}</strong>
                          <span>
                            {connector.type === "local" && typeof connector.config.root_path === "string"
                              ? connector.config.root_path
                              : connector.type === "google_drive"
                              ? "Google Drive"
                              : connector.type === "sharepoint"
                              ? "SharePoint / OneDrive"
                              : connector.type === "notion"
                              ? "Notion"
                              : connector.type}
                          </span>
                        </div>
                      </div>
                      <div className="source-actions">
                        <button
                          className="update-btn"
                          type="button"
                          disabled={sourcesBusy}
                          onClick={() => void syncConnector(connector.id)}
                        >
                          {sourcesBusy ? (
                            <Loader2 size={15} className="spin" />
                          ) : (
                            <RefreshCw size={15} />
                          )}
                          Mettre à jour
                        </button>
                        <button
                          className="delete-btn"
                          type="button"
                          disabled={sourcesBusy}
                          onClick={() => void deleteConnector(connector.id)}
                          aria-label="Supprimer cette source"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="sources-section">
              <h2>Importer un fichier</h2>
              <div
                className={`upload-zone ${uploadDragging ? "dragging" : ""} ${sourcesBusy ? "disabled" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setUploadDragging(true); }}
                onDragLeave={() => setUploadDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setUploadDragging(false);
                  void handleFileUpload(e.dataTransfer.files);
                }}
                onClick={() => !sourcesBusy && fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt"
                  multiple
                  style={{ display: "none" }}
                  onChange={(e) => void handleFileUpload(e.target.files)}
                />
                {uploadProgress ? (
                  <>
                    <Loader2 size={28} className="spin upload-zone-icon" />
                    <p>{uploadProgress}</p>
                  </>
                ) : (
                  <>
                    <Upload size={28} className="upload-zone-icon" />
                    <p>Glissez vos fichiers ici ou <span className="upload-link">cliquez pour choisir</span></p>
                    <span>PDF, DOCX, TXT · 50 Mo maximum</span>
                  </>
                )}
              </div>
            </section>

            <section className="sources-section">
              <h2>Connecter une source externe</h2>
              <form className="add-source-form" onSubmit={createConnector}>
                <label>
                  Nom de la source
                  <input
                    value={connectorName}
                    onChange={(e) => setConnectorName(e.target.value)}
                    placeholder="ex. Documents RH"
                    required
                  />
                </label>

                <label>
                  Type de connexion
                  <select
                    value={connectorType}
                    onChange={(e) => setConnectorType(e.target.value as "local" | "google_drive" | "sharepoint" | "notion")}
                  >
                    <option value="local">Dossier local</option>
                    <option value="google_drive">Google Drive</option>
                    <option value="sharepoint">SharePoint / OneDrive</option>
                    <option value="notion">Notion</option>
                  </select>
                </label>

                {connectorType === "local" && (
                  <label>
                    Chemin du dossier
                    <input
                      value={rootPath}
                      onChange={(e) => setRootPath(e.target.value)}
                      placeholder="/data/mon-dossier"
                      required
                    />
                  </label>
                )}

                {connectorType === "google_drive" && (
                  <>
                    <label>
                      Clé JSON du compte de service
                      <textarea
                        className="json-textarea"
                        value={gdServiceAccount}
                        onChange={(e) => setGdServiceAccount(e.target.value)}
                        placeholder={'{\n  "type": "service_account",\n  "project_id": "...",\n  ...\n}'}
                        rows={6}
                        required
                      />
                    </label>
                    <label>
                      ID du dossier Google Drive <span className="field-optional">(optionnel)</span>
                      <input
                        value={gdFolderId}
                        onChange={(e) => setGdFolderId(e.target.value)}
                        placeholder="ex. 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
                      />
                    </label>
                  </>
                )}

                {connectorType === "notion" && (
                  <>
                    <label>
                      Token d&apos;intégration Notion
                      <input
                        type="password"
                        value={notionToken}
                        onChange={(e) => setNotionToken(e.target.value)}
                        placeholder="secret_..."
                        required
                      />
                    </label>
                    <label>
                      ID de la base de données <span className="field-optional">(optionnel)</span>
                      <input
                        value={notionDatabaseId}
                        onChange={(e) => setNotionDatabaseId(e.target.value)}
                        placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                      />
                    </label>
                    <label>
                      ID de la page racine <span className="field-optional">(optionnel)</span>
                      <input
                        value={notionPageId}
                        onChange={(e) => setNotionPageId(e.target.value)}
                        placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                      />
                    </label>
                  </>
                )}

                {connectorType === "sharepoint" && (
                  <>
                    <label>
                      ID du tenant Azure AD
                      <input
                        value={spTenantId}
                        onChange={(e) => setSpTenantId(e.target.value)}
                        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                        required
                      />
                    </label>
                    <label>
                      ID de l&apos;application (client)
                      <input
                        value={spClientId}
                        onChange={(e) => setSpClientId(e.target.value)}
                        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                        required
                      />
                    </label>
                    <label>
                      Secret de l&apos;application
                      <input
                        type="password"
                        value={spClientSecret}
                        onChange={(e) => setSpClientSecret(e.target.value)}
                        placeholder="Valeur du secret client"
                        required
                      />
                    </label>
                    <label>
                      ID du site SharePoint <span className="field-optional">(optionnel)</span>
                      <input
                        value={spSiteId}
                        onChange={(e) => setSpSiteId(e.target.value)}
                        placeholder="ex. contoso.sharepoint.com,abc123,def456"
                      />
                    </label>
                    <label>
                      ID du drive <span className="field-optional">(optionnel)</span>
                      <input
                        value={spDriveId}
                        onChange={(e) => setSpDriveId(e.target.value)}
                        placeholder="ex. b!abc123..."
                      />
                    </label>
                  </>
                )}

                <button className="connect-btn" type="submit" disabled={sourcesBusy}>
                  {sourcesBusy ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
                  Connecter cette source
                </button>
              </form>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
