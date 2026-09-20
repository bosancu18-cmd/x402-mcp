import { z } from "zod";
import { API } from "./client";
import { readOperatorToken } from "../lib/operatorToken";

const mailrailHealthSchema = z
  .object({
    ok: z.boolean(),
    enabled: z.boolean(),
    provider: z.string(),
  })
  .passthrough();

const mailrailMessageSchema = z
  .object({
    ts: z.string().optional(),
    event_id: z.string().optional(),
    inbound_id: z.string().optional(),
    to: z.string().optional(),
    from: z.string().optional(),
    sender: z.string().optional(),
    subject: z.string().optional(),
    body: z.string().optional(),
    provider: z.string().optional(),
    status: z.string().optional(),
    delivered: z.boolean().optional(),
    metadata: z.record(z.string(), z.unknown()).optional(),
  })
  .passthrough();

const mailrailStatsSchema = z
  .object({
    enabled: z.boolean().optional(),
    provider: z.string().optional(),
    from_address: z.string().nullable().optional(),
    admin_recipient: z.string().nullable().optional(),
    outbound_total: z.number().optional(),
    inbound_total: z.number().optional(),
    dedup_keys_cached: z.number().optional(),
    outbox_count: z.number().optional(),
    inbox_count: z.number().optional(),
  })
  .passthrough();

const ledgerSchema = z.object({
  events: z.array(mailrailMessageSchema),
  count: z.number(),
});

const inboxSchema = z.object({
  inbox: z.array(mailrailMessageSchema),
  count: z.number(),
});

export type MailrailHealth = z.infer<typeof mailrailHealthSchema>;
export type MailrailMessage = z.infer<typeof mailrailMessageSchema>;
export type MailrailStats = z.infer<typeof mailrailStatsSchema>;

export type MailrailView = {
  health: MailrailHealth;
  stats: MailrailStats;
  outbox: MailrailMessage[];
  inbox: MailrailMessage[];
};

export type MailrailLoadResult =
  | { ok: true; data: MailrailView }
  | {
      ok: false;
      reason: "unauthorized" | "network" | "invalid";
      message: string;
      health: MailrailHealth | null;
    };

export function resolveMailrailApiBase(override?: string): string {
  if (override !== undefined) return override.replace(/\/$/, "");
  return (API || "").replace(/\/$/, "");
}

function operatorHeaders(token: string | null): HeadersInit {
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function parseJson(res: Response): Promise<unknown> {
  return res.json() as Promise<unknown>;
}

async function fetchHealth(apiBase: string): Promise<MailrailHealth> {
  const res = await fetch(`${apiBase}/mailrail/health`);
  if (!res.ok) {
    throw new Error(`/mailrail/health failed: ${res.status}`);
  }
  return mailrailHealthSchema.parse(await parseJson(res));
}

export async function loadMailrailView(options?: {
  apiBase?: string;
  token?: string | null;
  limit?: number;
}): Promise<MailrailLoadResult> {
  const apiBase = resolveMailrailApiBase(options?.apiBase);
  const token = options?.token === undefined ? readOperatorToken() : options.token;
  const limit = options?.limit ?? 50;

  let health: MailrailHealth | null = null;
  try {
    health = await fetchHealth(apiBase);
  } catch (err) {
    return {
      ok: false,
      reason: "network",
      message: err instanceof Error ? err.message : "MailRail health fetch failed",
      health: null,
    };
  }

  if (!token) {
    return {
      ok: false,
      reason: "unauthorized",
      message: "Inbox and outbox require OPERATOR_TOKEN. Health is public and does not include message bodies.",
      health,
    };
  }

  try {
    const headers = operatorHeaders(token);
    const [statsRes, ledgerRes, inboxRes] = await Promise.all([
      fetch(`${apiBase}/mailrail/stats`, { headers }),
      fetch(`${apiBase}/mailrail/ledger?limit=${limit}`, { headers }),
      fetch(`${apiBase}/mailrail/inbox?limit=${limit}`, { headers }),
    ]);

    if (statsRes.status === 401 || ledgerRes.status === 401 || inboxRes.status === 401) {
      return {
        ok: false,
        reason: "unauthorized",
        message: "OPERATOR_TOKEN was rejected. MailRail ledgers stay closed without a valid bearer.",
        health,
      };
    }

    if (!statsRes.ok || !ledgerRes.ok || !inboxRes.ok) {
      return {
        ok: false,
        reason: "network",
        message: `MailRail ledger fetch failed (${statsRes.status}/${ledgerRes.status}/${inboxRes.status})`,
        health,
      };
    }

    const stats = mailrailStatsSchema.parse(await parseJson(statsRes));
    const ledger = ledgerSchema.parse(await parseJson(ledgerRes));
    const inbox = inboxSchema.parse(await parseJson(inboxRes));
    return {
      ok: true,
      data: {
        health,
        stats,
        outbox: ledger.events,
        inbox: inbox.inbox,
      },
    };
  } catch (err) {
    return {
      ok: false,
      reason: "invalid",
      message: err instanceof Error ? err.message : "MailRail response did not match schema",
      health,
    };
  }
}

export function outboxCount(stats: MailrailStats | null, fallback: number): number {
  if (!stats) return fallback;
  return stats.outbound_total ?? stats.outbox_count ?? fallback;
}

export function inboxCount(stats: MailrailStats | null, fallback: number): number {
  if (!stats) return fallback;
  return stats.inbound_total ?? stats.inbox_count ?? fallback;
}

export function messageFailed(message: MailrailMessage): boolean {
  return message.status === "dispatch_failed" || message.delivered === false;
}

export function messagePeer(kind: "outbox" | "inbox", message: MailrailMessage): string {
  switch (kind) {
    case "outbox":
      return message.to ?? "—";
    case "inbox":
      return message.sender ?? message.from ?? "—";
    default: {
      const exhaustive: never = kind;
      return exhaustive;
    }
  }
}
