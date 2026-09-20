/**
 * @vitest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MailRailPanel } from "./MailRailPanel";
import { clearOperatorToken } from "@dashboard/lib/operatorToken";

describe("MailRailPanel", () => {
  afterEach(() => {
    clearOperatorToken();
    vi.unstubAllGlobals();
  });

  it("renders AgentMail heading on the operator console", async () => {
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/mailrail/health")) {
        return new Response(JSON.stringify({ ok: true, enabled: false, provider: "mock" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`unexpected ${url}`);
    });
    render(<MailRailPanel refreshKey={1} apiBase="" />);
    expect(screen.getByText("AgentMail")).toBeInTheDocument();
    expect(await screen.findByLabelText("OPERATOR_TOKEN")).toBeInTheDocument();
  });
});
