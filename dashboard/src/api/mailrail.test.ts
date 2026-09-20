/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadMailrailView, messagePeer, outboxCount } from "./mailrail";
import { clearOperatorToken, writeOperatorToken } from "../lib/operatorToken";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("loadMailrailView", () => {
  afterEach(() => {
    clearOperatorToken();
    vi.unstubAllGlobals();
  });

  it("loads health without a token and does not call ledgers", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/mailrail/health")) {
        return jsonResponse(200, { ok: true, enabled: false, provider: "mock" });
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadMailrailView({ apiBase: "http://127.0.0.1:8402", token: null });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.reason).toBe("unauthorized");
    expect(result.health?.enabled).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("parses inbox and outbox when bearer is accepted", async () => {
    writeOperatorToken("s3cret");
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/mailrail/health")) {
        return jsonResponse(200, { ok: true, enabled: false, provider: "mock" });
      }
      if (url.includes("/mailrail/stats")) {
        return jsonResponse(200, { outbound_total: 1, inbound_total: 1, provider: "mock" });
      }
      if (url.includes("/mailrail/ledger")) {
        return jsonResponse(200, {
          count: 1,
          events: [{ subject: "catalog", to: "ops@localhost", ts: "2026-09-20T00:00:00Z" }],
        });
      }
      if (url.includes("/mailrail/inbox")) {
        return jsonResponse(200, {
          count: 1,
          inbox: [{ subject: "hello", from: "peer-agent", inbound_id: "abc" }],
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });

    const result = await loadMailrailView({ apiBase: "" });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.data.outbox[0]?.subject).toBe("catalog");
    expect(result.data.inbox[0]?.from).toBe("peer-agent");
    expect(outboxCount(result.data.stats, 0)).toBe(1);
    expect(messagePeer("inbox", result.data.inbox[0]!)).toBe("peer-agent");
  });

  it("maps 401 ledger responses to unauthorized", async () => {
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/mailrail/health")) {
        return jsonResponse(200, { ok: true, enabled: true, provider: "webhook" });
      }
      return jsonResponse(401, { error: "unauthorized" });
    });

    const result = await loadMailrailView({ apiBase: "", token: "nope" });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.reason).toBe("unauthorized");
    expect(result.health?.provider).toBe("webhook");
  });
});
