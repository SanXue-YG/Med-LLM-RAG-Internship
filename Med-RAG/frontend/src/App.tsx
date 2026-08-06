import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, SessionDetail, SessionSummary, SessionTurn } from "./api";
import { MarkdownView } from "./MarkdownView";
import "./styles.css";

type Msg = {
  role: "user" | "assistant";
  text: string;
  sources?: Array<Record<string, unknown>>;
};

const HELP_CARDS = [
  {
    title: "示例问答",
    body: "试问：What is the Plasmodium falciparum transcriptome?",
    action: "ask" as const,
    payload: "What is the Plasmodium falciparum transcriptome?",
  },
  {
    title: "API 说明",
    body: "打开后端 Swagger：/docs（sessions / qa / ingest）",
    action: "link" as const,
    payload: "http://127.0.0.1:8000/docs",
  },
  {
    title: "代码原理",
    body: "点击查看包内代码说明文档（Markdown）",
    action: "doc" as const,
    payload: "code",
  },
  {
    title: "流程图",
    body: "点击查看包内流程图文档（Markdown）",
    action: "doc" as const,
    payload: "flow",
  },
];

function turnsToMessages(turns: SessionTurn[]): Msg[] {
  const out: Msg[] = [];
  for (const t of turns) {
    out.push({ role: "user", text: t.query || "" });
    const sources =
      (t.meta?.sources as Array<Record<string, unknown>> | undefined) || undefined;
    out.push({
      role: "assistant",
      text: t.answer || "",
      sources,
    });
  }
  return out;
}

function sourceLabel(s: Record<string, unknown>): string {
  return String(s.pmcid || s.doc_id || s.chunk_id || "").trim();
}

export default function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [search, setSearch] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [indexReady, setIndexReady] = useState<boolean | null>(null);
  const [statusNote, setStatusNote] = useState("checking…");
  const [showIngest, setShowIngest] = useState(false);
  const [ingestMsg, setIngestMsg] = useState<string | null>(null);
  const [docOpen, setDocOpen] = useState<{ title: string; markdown: string } | null>(null);
  const [docLoading, setDocLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const chatPaneRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshSessions = useCallback(async (q?: string) => {
    const data = await api.listSessions(q);
    setSessions(data.items || []);
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const ready = await api.ready();
      const idx = (ready as { index?: { ready?: boolean } }).index;
      setIndexReady(Boolean(idx?.ready ?? ready.ready));
      setStatusNote(idx?.ready ? "index ready" : "index missing — use paperclip to upload");
    } catch {
      setIndexReady(false);
      setStatusNote("API offline");
    }
  }, []);

  useEffect(() => {
    refreshSessions().catch((e) => setError(String(e.message || e)));
    refreshHealth();
  }, [refreshSessions, refreshHealth]);

  useEffect(() => {
    const t = setTimeout(() => {
      refreshSessions(search.trim() || undefined).catch(() => undefined);
    }, 250);
    return () => clearTimeout(t);
  }, [search, refreshSessions]);

  useEffect(() => {
    // Scroll only inside the chat pane, never the whole page / sidebar
    const pane = chatPaneRef.current;
    if (!pane || !bottomRef.current) return;
    pane.scrollTo({ top: pane.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  const openSession = async (id: string) => {
    setError(null);
    const detail: SessionDetail = await api.getSession(id);
    setSessionId(detail.session_id);
    setMessages(turnsToMessages(detail.turns || []));
  };

  const newChat = async () => {
    setError(null);
    const created = await api.createSession();
    setSessionId(created.session_id);
    setMessages([]);
    await refreshSessions(search.trim() || undefined);
  };

  const deleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await api.deleteSession(id);
    if (sessionId === id) {
      setSessionId(null);
      setMessages([]);
    }
    await refreshSessions(search.trim() || undefined);
  };

  const send = async (text?: string) => {
    const query = (text ?? draft).trim();
    if (!query || busy) return;
    setBusy(true);
    setError(null);
    setDraft("");
    setMessages((m) => [...m, { role: "user", text: query }]);
    try {
      let sid = sessionId;
      if (!sid) {
        const created = await api.createSession();
        sid = created.session_id;
        setSessionId(sid);
      }
      const result = await api.ask(query, sid);
      const finalSid = result.session_id || sid;
      setSessionId(finalSid);
      // Reload from disk so UI matches persisted turns/title/sources
      await openSession(finalSid);
      await refreshSessions(search.trim() || undefined);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setMessages((m) => [...m, { role: "assistant", text: `**错误：** ${msg}` }]);
    } finally {
      setBusy(false);
    }
  };

  const openDoc = async (slug: string) => {
    setDocLoading(true);
    setError(null);
    try {
      const doc = await api.getDoc(slug);
      setDocOpen({ title: doc.title, markdown: doc.markdown });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDocLoading(false);
    }
  };

  const onCard = (card: (typeof HELP_CARDS)[number]) => {
    if (card.action === "ask") void send(card.payload);
    if (card.action === "link") window.open(card.payload, "_blank");
    if (card.action === "doc") void openDoc(card.payload);
  };

  const onUpload = async (file: File) => {
    setIngestMsg("上传并索引中…");
    try {
      const result = await api.upload(file);
      setIngestMsg(
        `完成：chunks+${(result.chroma as { added?: number })?.added ?? 0}，documents+${result.documents_upserted ?? 0}`,
      );
      await refreshHealth();
    } catch (err) {
      setIngestMsg(err instanceof Error ? err.message : String(err));
    }
  };

  const title = useMemo(() => {
    const hit = sessions.find((s) => s.session_id === sessionId);
    if (hit?.title) return hit.title;
    const firstUser = messages.find((m) => m.role === "user");
    if (firstUser?.text) {
      const q = firstUser.text.trim();
      return q.length > 48 ? `${q.slice(0, 48)}…` : q;
    }
    return "New chat";
  }, [sessions, sessionId, messages]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="brand">
            <div className="brand-mark">M</div>
            <div>
              <h1>Med-RAG</h1>
              <p>Medical literature QA demo</p>
            </div>
          </div>
          <button className="btn" type="button" onClick={() => void newChat()}>
            + New Chat
          </button>
          <label className="search">
            <span aria-hidden>⌕</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search chats…"
            />
          </label>
        </div>
        <div className="session-list">
          {sessions.map((s) => (
            <div className="session-row" key={s.session_id}>
              <button
                type="button"
                className={`session-item ${s.session_id === sessionId ? "active" : ""}`}
                onClick={() => void openSession(s.session_id)}
              >
                <div className="title">{s.title || "Untitled"}</div>
                <div className="meta">{s.turn_count} turns</div>
              </button>
              <button
                type="button"
                className="icon-btn"
                title="Delete"
                onClick={(e) => void deleteSession(s.session_id, e)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div>
            <strong>{title}</strong>
          </div>
          <div className="pill">{indexReady ? "●" : "○"} {statusNote}</div>
        </div>

        <div className="chat-pane" ref={chatPaneRef}>
          {messages.length === 0 ? (
            <div className="empty">
              <h2>How can I help with the literature today?</h2>
              <p>
                Local Medical RAG demo backed by the stage 11/12 API. Ask a question, explore the
                pipeline docs, or attach new PMC XML / JSONL to update the sample index.
              </p>
              <div className="cards">
                {HELP_CARDS.map((c) => (
                  <button key={c.title} type="button" className="card" onClick={() => onCard(c)}>
                    <strong>{c.title}</strong>
                    <span>{c.body}</span>
                  </button>
                ))}
              </div>
              {docLoading ? <p className="hint">加载文档中…</p> : null}
            </div>
          ) : (
            <div className="messages">
              {messages.map((m, i) => (
                <div key={i} className={`bubble ${m.role}`}>
                  {m.role === "assistant" ? (
                    <>
                      <MarkdownView content={m.text} />
                      {m.sources && m.sources.length > 0 ? (
                        <div className="sources">
                          <strong>Sources</strong>
                          <ul>
                            {m.sources.slice(0, 12).map((s, j) => {
                              const label = sourceLabel(s);
                              if (!label) return null;
                              const score = s.score ?? s.rerank_score;
                              return (
                                <li key={`${label}-${j}`}>
                                  {label}
                                  {score != null ? ` · ${Number(score).toFixed?.(3) ?? score}` : ""}
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      ) : null}
                    </>
                  ) : (
                    m.text
                  )}
                </div>
              ))}
              {busy ? (
                <div className="bubble assistant">
                  <MarkdownView content={"*正在检索与生成…*"} />
                </div>
              ) : null}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div className="composer-wrap">
          {error ? <div className="hint error">{error}</div> : null}
          <div className="composer">
            <button
              type="button"
              className="btn ghost"
              title="上传语料更新索引"
              onClick={() => setShowIngest(true)}
            >
              📎
            </button>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about PMC literature…"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
            <button
              className="send"
              type="button"
              disabled={busy || !draft.trim()}
              onClick={() => void send()}
            >
              ↑
            </button>
          </div>
          <div className="hint">Enter 发送 · Shift+Enter 换行 · 回形针上传额外数据集</div>
        </div>
      </main>

      {showIngest ? (
        <div className="modal-backdrop" onClick={() => setShowIngest(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>语料更新</h3>
            <p>
              上传 PMC XML / slim JSONL / chunks JSON，将写入 <code>Med-RAG/data/</code>{" "}
              样本索引（不依赖仓库外路径）。
            </p>
            <input
              ref={fileRef}
              type="file"
              accept=".xml,.jsonl,.json"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void onUpload(f);
              }}
            />
            {ingestMsg ? <p className="hint">{ingestMsg}</p> : null}
            <div style={{ marginTop: 16, display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" className="btn ghost" onClick={() => setShowIngest(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {docOpen ? (
        <div className="modal-backdrop" onClick={() => setDocOpen(null)}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{docOpen.title}</h3>
              <button type="button" className="icon-btn" onClick={() => setDocOpen(null)}>
                ×
              </button>
            </div>
            <div className="modal-scroll">
              <MarkdownView content={docOpen.markdown} />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
