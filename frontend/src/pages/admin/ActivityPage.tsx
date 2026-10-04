import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, Search } from "lucide-react";

import { ApiError } from "../../lib/api";
import {
  ACTION_OPTIONS,
  fetchActivity,
  fetchActors,
  type ActivityEntry,
  type ActivityPage as Page,
  type ActorRef,
} from "../../lib/activity";
import { AdminChrome } from "./AdminChrome";

const PAGE_SIZE = 25;

/** "7 Sep 2026, 00:31" — date and time both matter in an audit trail. */
function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Field names come from the model; underscores are not for reading. */
function fieldLabel(name: string): string {
  return name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

/** auditlog stringifies every value, so "None" is what an empty field looks like. */
function formatValue(value: string | null): string {
  if (value == null || value === "" || value === "None") return "—";
  if (value === "True") return "yes";
  if (value === "False") return "no";
  return value;
}

const ACTION_TONE: Record<string, string> = {
  sign_in: "pill-ok",
  sign_out: "pill-muted",
  sign_in_failed: "pill-warn",
  delete: "pill-warn",
  create: "pill-ok",
  invite_sent: "pill-brand",
};

export default function ActivityPage() {
  const [page, setPage] = useState<Page | null>(null);
  const [actors, setActors] = useState<ActorRef[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState("");
  const [action, setAction] = useState("");
  const [userId, setUserId] = useState<number | null>(null);
  const [pageNo, setPageNo] = useState(1);

  // Debounced so typing in the search box does not fire a request per key.
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 250);
    return () => clearTimeout(timer);
  }, [search]);

  // Any filter change invalidates the page number, so the two move together
  // in the handler rather than in an effect that reacts to the first.
  const changeSearch = (value: string) => {
    setSearch(value);
    setPageNo(1);
  };
  const changeAction = (value: string) => {
    setAction(value);
    setPageNo(1);
  };
  const changeActor = (value: number | null) => {
    setUserId(value);
    setPageNo(1);
  };

  const load = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      try {
        const result = await fetchActivity(
          { search: debouncedSearch, action, userId, page: pageNo, pageSize: PAGE_SIZE },
          signal,
        );
        if (signal.aborted) return;
        setPage(result);
        setError(null);
      } catch (err) {
        if (signal.aborted) return;
        setError(
          err instanceof ApiError && err.status === 403
            ? "Your account does not have permission to view the activity log."
            : "Could not load the activity log. Is the API running?",
        );
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    },
    [debouncedSearch, action, userId, pageNo],
  );

  useEffect(() => {
    const controller = new AbortController();
    // The lint rule cannot express "a new query has started": the busy flag
    // has to be raised when the filters change, which is exactly here. The
    // request is aborted on cleanup, so no stale page can land.
    // eslint-disable-next-line react/set-state-in-effect
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    const controller = new AbortController();
    // Secondary to the feed: an empty list just means no actor filter.
    fetchActors(controller.signal)
      .then((rows) => !controller.signal.aborted && setActors(rows))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  const entries = page?.entries ?? null;
  const summary = useMemo(() => {
    if (!page) return "Everything that has happened in this deployment.";
    const from = (page.page - 1) * page.pageSize + 1;
    const to = Math.min(page.page * page.pageSize, page.count);
    return page.count === 0
      ? "No matching activity."
      : `${from}–${to} of ${page.count} ${page.count === 1 ? "entry" : "entries"}`;
  }, [page]);

  return (
    <AdminChrome>
      <section className="admin">
        <div className="page-head">
          <div>
            <h1>Activity</h1>
            <p>{summary}</p>
          </div>
        </div>

        <div className="activity-filters">
          <div className="search-field">
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              value={search}
              onChange={(e) => changeSearch(e.target.value)}
              placeholder="Search by gene, account or address…"
              aria-label="Search activity"
            />
          </div>

          <label className="visually-hidden" htmlFor="activity-action">
            Filter by action
          </label>
          <select
            id="activity-action"
            className="select-field"
            value={action}
            onChange={(e) => changeAction(e.target.value)}
          >
            {ACTION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>

          <label className="visually-hidden" htmlFor="activity-actor">
            Filter by person
          </label>
          <select
            id="activity-actor"
            className="select-field"
            value={userId ?? ""}
            onChange={(e) => changeActor(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Everyone</option>
            {actors.map((a) => (
              <option key={a.id} value={a.id}>
                {a.email}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <div className="error-card" role="alert">
            {error}
          </div>
        )}

        <div className="card">
          {loading && !entries && (
            <div className="card-empty">
              <Loader2 size={22} className="spin" aria-hidden="true" />
              <p>Loading activity…</p>
            </div>
          )}

          {entries && entries.length === 0 && (
            <div className="card-empty">
              <p>Nothing matches these filters.</p>
            </div>
          )}

          {entries && entries.length > 0 && (
            <ul className="activity-list" aria-busy={loading}>
              {entries.map((entry) => (
                <ActivityRow key={entry.id} entry={entry} />
              ))}
            </ul>
          )}
        </div>

        {page && page.totalPages > 1 && (
          <nav className="pager" aria-label="Activity pages">
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={page.page <= 1 || loading}
              onClick={() => setPageNo((n) => Math.max(1, n - 1))}
            >
              <ChevronLeft size={15} aria-hidden="true" />
              Previous
            </button>
            <span className="pager-status">
              Page {page.page} of {page.totalPages}
            </span>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={page.page >= page.totalPages || loading}
              onClick={() => setPageNo((n) => n + 1)}
            >
              Next
              <ChevronRight size={15} aria-hidden="true" />
            </button>
          </nav>
        )}

        <p className="admin-note">
          Model changes come from django-auditlog; sign-ins, gene views and
          exports are recorded by the application. Repeat views of the same
          gene by the same person collapse into one entry for five minutes.
          Passwords are never recorded.
        </p>
      </section>
    </AdminChrome>
  );
}

function ActivityRow({ entry }: { entry: ActivityEntry }) {
  const changed = Object.entries(entry.changes ?? {});
  const tone = ACTION_TONE[entry.action] ?? "pill-brand";

  return (
    <li className="activity-item">
      <div className="activity-main">
        <span className={`pill ${tone}`}>{entry.actionDisplay}</span>
        <span className="activity-actor">{entry.actorName || entry.actorEmail || "System"}</span>
        {entry.target && <span className="activity-target">{entry.target}</span>}
      </div>

      {changed.length > 0 && (
        <ul className="activity-diff">
          {changed.map(([field, pair]) => (
            <li key={field}>
              <span className="activity-field">{fieldLabel(field)}</span>
              <span className="activity-old">{formatValue(pair.old)}</span>
              <span className="activity-arrow" aria-label="changed to">
                →
              </span>
              <span className="activity-new">{formatValue(pair.new)}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="activity-meta">
        <time dateTime={entry.timestamp}>{formatWhen(entry.timestamp)}</time>
        {entry.remoteAddr && <span className="activity-addr">{entry.remoteAddr}</span>}
      </div>
    </li>
  );
}
