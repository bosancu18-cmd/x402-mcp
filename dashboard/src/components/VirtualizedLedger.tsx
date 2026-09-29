
import type { LedgerRow } from "../api/client";
import { CopyButton } from "./CopyButton";
import { basescanUrl, truncateHash } from "../utils/decode402";
import { ledgerRowAtomic } from "../utils/ledger";
import { formatUsdcAtomic } from "../utils/usdc";
import { relativeTime } from "../utils/time";

type Props = {
  rows: LedgerRow[];
  kind: "spend" | "revenue";
  filterNetwork?: string;
  filterAgent?: string;
};

export function VirtualizedLedger({ rows, kind, filterNetwork, filterAgent }: Props) {
  const filtered = rows.filter((row) => {
    if (filterNetwork && String(row.network ?? "") !== filterNetwork) return false;
    if (filterAgent && String(row.agent_id ?? "") !== filterAgent) return false;
    return true;
  });

  const color = kind === "spend" ? "var(--usdc)" : "var(--green)";

  if (filtered.length === 0) {
    return <div style={{ color: "var(--text-muted)", fontSize: 13, padding: 8 }}>No matching records.</div>;
  }

  return (
    <div style={{ maxHeight: 220, overflow: "auto" }}>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {filtered.map((row, i) => {
          const atomic = ledgerRowAtomic(row);
          const ts = String(row.ts ?? "");

          return (
            <li
              key={i}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "8px 0",
                borderBottom: "1px solid var(--border)",
                fontSize: 12,
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ color: "var(--text-muted)" }}>
                  {ts ? relativeTime(ts) : "unknown date"} •{" "}
                  <span style={{ color: "var(--text)" }}>{String(row.agent_id ?? row.product_id ?? "unknown")}</span>
                </div>
                <div className="mono" style={{ marginTop: 4 }}>
                  <a href={basescanUrl(row.network ?? "eip155:8453", row.tx)} target="_blank" rel="noreferrer" style={{ color: "var(--amber)" }}>
                    {truncateHash(row.tx)}
                  </a>
                  {row.run_id && (
                    <span style={{ marginLeft: 8, color: "var(--text-muted)" }}>
                      run: {truncateHash(row.run_id)}
                      <CopyButton value={row.run_id} />
                    </span>
                  )}
                </div>
              </div>
              <div className="mono" style={{ color, fontSize: 13, fontWeight: "bold", marginLeft: 16 }}>
                {kind === "revenue" ? "+" : "-"}{formatUsdcAtomic(atomic)}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
