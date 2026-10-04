/**
 * Client for the activity log.
 *
 * The API merges two backend sources into one feed — django-auditlog's model
 * diffs (`source: "change"`) and this project's auth/access events
 * (`source: "access"`) — so there is a single resource to page and filter.
 */

import { getJson, sendJson } from "./api";

export type ActivitySource = "change" | "access";

export interface ChangePair {
  old: string | null;
  new: string | null;
}

export interface ActivityEntry {
  /** Prefixed by source: the two tables number their rows independently. */
  id: string;
  source: ActivitySource;
  timestamp: string;
  actorId: number | null;
  actorEmail: string;
  actorName: string;
  action: string;
  actionDisplay: string;
  target: string;
  targetType: string | null;
  /** Field-level diff; only ever present on a `change` entry. */
  changes: Record<string, ChangePair> | null;
  metadata: Record<string, unknown>;
  remoteAddr: string | null;
}

export interface ActivityPage {
  entries: ActivityEntry[];
  count: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ActorRef {
  id: number;
  email: string;
}

export interface ActivityFilters {
  source?: ActivitySource | "";
  action?: string;
  userId?: number | null;
  search?: string;
  page?: number;
  pageSize?: number;
}

interface EntryWire {
  id: string;
  source: ActivitySource;
  timestamp: string;
  actor_id: number | null;
  actor_email: string;
  actor_name: string;
  action: string;
  action_display: string;
  target: string;
  target_type: string | null;
  changes: Record<string, ChangePair> | null;
  metadata: Record<string, unknown>;
  remote_addr: string | null;
}

interface PageWire {
  results: EntryWire[];
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

function toEntry(w: EntryWire): ActivityEntry {
  return {
    id: w.id,
    source: w.source,
    timestamp: w.timestamp,
    actorId: w.actor_id,
    actorEmail: w.actor_email,
    actorName: w.actor_name,
    action: w.action,
    actionDisplay: w.action_display,
    target: w.target,
    targetType: w.target_type,
    changes: w.changes,
    metadata: w.metadata ?? {},
    remoteAddr: w.remote_addr,
  };
}

export async function fetchActivity(
  filters: ActivityFilters,
  signal?: AbortSignal,
): Promise<ActivityPage> {
  const params = new URLSearchParams();
  if (filters.source) params.set("source", filters.source);
  if (filters.action) params.set("action", filters.action);
  if (filters.userId != null) params.set("user_id", String(filters.userId));
  if (filters.search?.trim()) params.set("search", filters.search.trim());
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? 25));

  const wire = await getJson<PageWire>(`/activity/?${params}`, signal);
  return {
    entries: wire.results.map(toEntry),
    count: wire.count,
    page: wire.page,
    pageSize: wire.page_size,
    totalPages: wire.total_pages,
  };
}

export function fetchActors(signal?: AbortSignal): Promise<ActorRef[]> {
  return getJson<ActorRef[]>("/activity/actors/", signal);
}

/**
 * Report an action only the browser witnesses.
 *
 * The PNG is rendered and saved client-side, so nothing reaches the server
 * unless the page says so. Failure is swallowed: a missing audit row must
 * never turn into a visible error on the export the user actually wanted.
 */
export function reportExport(symbol: string): void {
  void sendJson("POST", "/activity/report/", {
    action: "export_png",
    target: symbol,
  }).catch(() => {
    /* best effort */
  });
}

/** The actions the filter offers, grouped the way the log reads. */
export const ACTION_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All actions" },
  { value: "sign_in", label: "Signed in" },
  { value: "sign_in_failed", label: "Failed sign-in" },
  { value: "sign_out", label: "Signed out" },
  { value: "gene_view", label: "Viewed gene" },
  { value: "export_png", label: "Exported PNG" },
  { value: "invite_sent", label: "Sent invitation" },
  { value: "create", label: "Created" },
  { value: "update", label: "Updated" },
  { value: "delete", label: "Deleted" },
];
