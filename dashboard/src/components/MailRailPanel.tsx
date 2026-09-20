import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  inboxCount,
  loadMailrailView,
  messageFailed,
  messagePeer,
  outboxCount,
  type MailrailHealth,
  type MailrailLoadResult,
  type MailrailMessage,
} from "../api/mailrail";
import { clearOperatorToken, hasOperatorToken, writeOperatorToken } from "../lib/operatorToken";
import { PanelHelp } from "./PanelHelp";
import { relativeTime } from "../utils/time";

type Folder = "outbox" | "inbox";

export type MailRailPanelProps = {
  refreshKey?: number;
  apiBase?: string;
};

function folderTitle(folder: Folder): string {
  switch (folder) {
    case "outbox":
      return "Outbox";
    case "inbox":
      return "Inbox";
    default: {
      const exhaustive: never = folder;
      return exhaustive;
    }
  }
}

function liveLabel(health: MailrailHealth | null): string {
  if (!health) return "status unknown";
  if (health.enabled) return `live dispatch (${health.provider})`;
  return `ledger only · ${health.provider} · MAILRAIL_ENABLED=false`;
}

function messageRowId(folder: Folder, message: MailrailMessage, index: number): string {
  return message.event_id ?? message.inbound_id ?? `${folder}-${index}`;
}

export function MailRailPanel({ refreshKey = 0, apiBase }: MailRailPanelProps) {
  const [tokenDraft, setTokenDraft] = useState("");
  const [tokenPresent, setTokenPresent] = useState(hasOperatorToken);
  const [folder, setFolder] = useState<Folder>("outbox");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [load, setLoad] = useState<MailrailLoadResult | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await loadMailrailView({ apiBase, limit: 50 });
      if (!cancelled) setLoad(result);
    })();
    return () => {
      cancelled = true;
    };
  }, [apiBase, refreshKey, tokenPresent, reloadNonce]);

  const health = load && (load.ok ? load.data.health : load.health);
  const stats = load?.ok ? load.data.stats : null;
  const outbox = load?.ok ? load.data.outbox : [];
  const inbox = load?.ok ? load.data.inbox : [];
  const items = folder === "outbox" ? outbox : inbox;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((m) => {
      const hay = `${m.subject ?? ""} ${m.body ?? ""} ${messagePeer(folder, m)}`.toLowerCase();
      return hay.includes(q);
    });
  }, [folder, items, query]);

  useEffect(() => {
    if (filtered.length === 0) {
      setSelectedId(null);
      return;
    }
    const ids = filtered.map((m, i) => messageRowId(folder, m, i));
    if (selectedId && ids.includes(selectedId)) return;
    setSelectedId(ids[0] ?? null);
  }, [filtered, folder, selectedId]);

  const selected =
    filtered.find((m, i) => messageRowId(folder, m, i) === selectedId) ?? null;

  const saveToken = (event: FormEvent) => {
    event.preventDefault();
    writeOperatorToken(tokenDraft);
    setTokenDraft("");
    setTokenPresent(hasOperatorToken());
  };

  const clearToken = () => {
    clearOperatorToken();
    setTokenPresent(false);
    setLoad(null);
  };

  return (
    <section id="panel-mailrail" className="panel" style={{ gridColumn: "span 12" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0 }}>
          AgentMail
          <PanelHelp term="AgentMail" title="AgentMail" />
        </h3>
        <span className="mono" style={{ color: health?.enabled ? "var(--green)" : "var(--amber)", fontSize: 12 }}>
          {liveLabel(health)}
        </span>
      </div>
      <p style={{ color: "var(--text-muted)", fontSize: 13, margin: "8px 0 12px" }}>
        Settlement receipts, city-call alerts, and peer inbound. Not an x402 payment rail.
      </p>

      {load === null && (
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading MailRail…</p>
      )}

      {load && !load.ok && load.reason === "unauthorized" && (
        <form onSubmit={saveToken} style={{ marginBottom: 12 }}>
          <label style={{ display: "block", fontSize: 13, marginBottom: 6 }}>
            Operator token
            <input
              type="password"
              autoComplete="off"
              value={tokenDraft}
              onChange={(e) => setTokenDraft(e.target.value)}
              placeholder="OPERATOR_TOKEN"
              aria-label="OPERATOR_TOKEN"
              style={{ width: "100%", marginTop: 4 }}
            />
          </label>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <button type="submit">Unlock inbox / outbox</button>
            {tokenPresent && (
              <button type="button" onClick={clearToken}>
                Clear saved token
              </button>
            )}
            <span style={{ color: "var(--text-muted)", fontSize: 12 }}>{load.message}</span>
          </div>
        </form>
      )}

      {load && !load.ok && load.reason !== "unauthorized" && (
        <div style={{ marginBottom: 12 }}>
          <p style={{ color: "var(--red)", fontSize: 13, margin: "0 0 8px" }}>{load.message}</p>
          <button type="button" onClick={() => setReloadNonce((n) => n + 1)}>
            Retry MailRail
          </button>
        </div>
      )}

      {load?.ok && (
        <>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12, fontSize: 13 }}>
            <span className="mono">
              outbox {outboxCount(stats, outbox.length)} · inbox {inboxCount(stats, inbox.length)}
            </span>
            {tokenPresent && (
              <button type="button" onClick={clearToken} style={{ fontSize: 12 }}>
                Forget token
              </button>
            )}
          </div>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            {(["outbox", "inbox"] as const).map((id) => (
              <button
                key={id}
                type="button"
                aria-pressed={folder === id}
                onClick={() => {
                  setFolder(id);
                  setSelectedId(null);
                }}
                style={{
                  background: folder === id ? "var(--usdc)" : "transparent",
                  color: folder === id ? "#fff" : "var(--text)",
                }}
              >
                {folderTitle(id)}
              </button>
            ))}
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Search ${folderTitle(folder).toLowerCase()}`}
              aria-label="Search AgentMail"
              style={{ flex: 1, minWidth: 160 }}
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(240px, 1fr) minmax(240px, 1fr)", gap: 12 }}>
            <MailList
              folder={folder}
              items={filtered}
              selectedId={selectedId}
              onSelect={(id) => setSelectedId(id)}
            />
            <MailDetail folder={folder} message={selected} />
          </div>
        </>
      )}
    </section>
  );
}

function MailList({
  folder,
  items,
  selectedId,
  onSelect,
}: {
  folder: Folder;
  items: MailrailMessage[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (items.length === 0) {
    return (
      <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
        No {folderTitle(folder).toLowerCase()} messages.
      </p>
    );
  }
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0, maxHeight: 320, overflow: "auto" }}>
      {items.map((m, i) => {
        const id = messageRowId(folder, m, i);
        const active = id === selectedId;
        return (
          <li key={id}>
            <button
              type="button"
              onClick={() => onSelect(id)}
              style={{
                width: "100%",
                textAlign: "left",
                background: active ? "var(--panel-2, #161c24)" : "transparent",
                border: "none",
                borderBottom: "1px solid var(--border)",
                color: "var(--text)",
                padding: "8px 4px",
                cursor: "pointer",
              }}
            >
              <div className="mono" style={{ color: "var(--text-muted)", fontSize: 11 }}>
                {m.ts ? relativeTime(m.ts) : "—"}
                {messageFailed(m) ? " · failed" : ""}
              </div>
              <strong style={{ fontSize: 13 }}>{m.subject ?? "(no subject)"}</strong>
              <div style={{ color: "var(--text-muted)", fontSize: 12 }}>
                {folder === "outbox" ? "to" : "from"} {messagePeer(folder, m)}
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function MailDetail({ folder, message }: { folder: Folder; message: MailrailMessage | null }) {
  if (!message) {
    return (
      <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Select a message to read the body.</p>
    );
  }
  const callKind =
    message.metadata && typeof message.metadata.call_kind === "string"
      ? message.metadata.call_kind
      : null;
  return (
    <article>
      <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>{message.subject ?? "(no subject)"}</h4>
      <div className="mono" style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
        {folder === "outbox" ? "to" : "from"} {messagePeer(folder, message)}
        {message.status ? ` · ${message.status}` : ""}
        {callKind ? ` · ${callKind}` : ""}
        {message.event_id ? ` · ${message.event_id}` : ""}
        {message.inbound_id ? ` · ${message.inbound_id}` : ""}
      </div>
      <pre
        style={{
          whiteSpace: "pre-wrap",
          fontSize: 12,
          background: "#0b0f14",
          padding: 12,
          borderRadius: 8,
          maxHeight: 260,
          overflow: "auto",
        }}
      >
        {message.body || "(empty body)"}
      </pre>
    </article>
  );
}
