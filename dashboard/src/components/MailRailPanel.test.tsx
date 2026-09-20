/**
 * @vitest-environment jsdom
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MailRailPanel } from "./MailRailPanel";
import { clearOperatorToken, writeOperatorToken } from "../lib/operatorToken";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("MailRailPanel", () => {
  afterEach(() => {
    cleanup();
    clearOperatorToken();
    vi.unstubAllGlobals();
  });

  it("asks for OPERATOR_TOKEN before showing ledgers", async () => {
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/mailrail/health")) {
        return jsonResponse(200, { ok: true, enabled: false, provider: "mock" });
      }
      throw new Error(`unexpected ${url}`);
    });

    render(<MailRailPanel apiBase="" />);
    expect(screen.getByText("AgentMail")).toBeDefined();
    expect(await screen.findByLabelText("OPERATOR_TOKEN")).toBeDefined();
    expect(screen.getByText(/ledger only/i)).toBeDefined();
  });

  it("renders outbox subjects and opens a body pane", async () => {
    writeOperatorToken("s3cret");
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/mailrail/health")) {
        return jsonResponse(200, { ok: true, enabled: false, provider: "mock" });
      }
      if (url.includes("/mailrail/stats")) {
        return jsonResponse(200, { outbound_total: 1, inbound_total: 0 });
      }
      if (url.includes("/mailrail/ledger")) {
        return jsonResponse(200, {
          count: 1,
          events: [
            {
              event_id: "evt1",
              subject: "City catalog browse",
              to: "ops@localhost",
              body: "Call kind:  catalog",
              ts: new Date().toISOString(),
              status: "sent",
            },
          ],
        });
      }
      if (url.includes("/mailrail/inbox")) {
        return jsonResponse(200, { count: 0, inbox: [] });
      }
      throw new Error(`unexpected ${url}`);
    });

    render(<MailRailPanel apiBase="" />);
    expect(await screen.findByText("City catalog browse")).toBeDefined();
    expect(screen.getByText(/outbox 1 · inbox 0/)).toBeDefined();
    expect(await screen.findByText(/Call kind:\s+catalog/)).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: /City catalog browse/i }));
    expect(screen.getByText(/Call kind:\s+catalog/)).toBeDefined();
  });
});
