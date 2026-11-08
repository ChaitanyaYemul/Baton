import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  ArrowRight,
  ShieldCheck,
  Layers3,
  Files,
  GitBranch,
  CircleHelp,
  Clock3,
  Check,
  X,
  Search,
  Plus,
  LockKeyhole,
  ChevronRight,
  Download,
  LogOut,
  RefreshCw,
  AlertTriangle,
  Users,
  BookOpen,
  CheckCheck,
  Send,
  FileText,
} from "lucide-react";
import "./style.css";
import {
  ActionBoard,
  QuestionQueue,
  TeamPanel,
  JoinWorkspace,
  type Action,
  type Assignment,
} from "./Advanced";
import "./theme.css";

type Evidence = {
  source_id: string;
  quote: string;
  found: boolean;
  locator: string;
  source?: string;
};
type Claim = {
  id: string;
  text: string;
  owner: string;
  status?: string;
  type?: string;
  review?: string;
  date?: string;
  reason: string;
  restricted?: boolean;
  stale?: boolean;
  conflicts?: string[];
  evidence?: Evidence[];
  attestation?: { by: string; at: string };
  change?: string;
  changed_fields?: string[];
  previous?: Record<string, unknown>;
};
type Source = {
  id: string;
  name: string;
  kind: string;
  access: string;
  redactions: number;
  lines: number;
};
type Workspace = {
  project: string;
  user: { name: string; role: string; id: string };
  claims: Claim[];
  sources: Source[];
  mode: string;
  sudden_exit: boolean;
  demo: boolean;
  actions: Action[];
  questions: Assignment[];
  approved_claims: Claim[];
  receipt_stale: boolean;
  storage: string;
  versions: { number: number; at: string; by: string; count: number }[];
  audit: { at: string; actor: string; action: string; detail: string }[];
  acks: {
    role: string;
    user_id?: string;
    by: string;
    section: string;
    version: number;
    at: string;
  }[];
};
const nav = [
  { id: "overview", label: "Overview", icon: Layers3 },
  { id: "sources", label: "Sources", icon: Files },
  { id: "review", label: "Claim ledger", icon: ShieldCheck },
  { id: "questions", label: "Ask the leaver", icon: CircleHelp },
  { id: "timeline", label: "Timeline", icon: Clock3 },
  { id: "ownership", label: "Ownership", icon: Users },
  { id: "handover", label: "Handover", icon: BookOpen },
  { id: "history", label: "Versions & activity", icon: GitBranch },
  { id: "people", label: "Team access", icon: Users },
];
async function api(path: string, method = "GET", data?: unknown) {
  const response = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-Baton-Request": "1" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Request failed. Check your input and try again.",
    );
  return result;
}
function Badge({ value }: { value?: string }) {
  return (
    <span className={"badge " + value}>
      {value === "verified" ? "Quote verified" : value?.replaceAll("_", " ")}
    </span>
  );
}
function App() {
  const [authConfig, setAuthConfig] = useState<{
    demo: boolean;
    roles: string[];
  }>({ demo: false, roles: ["reviewer"] });
  const [joining, setJoining] = useState(false),
    [username, setUsername] = useState("");
  const [ws, setWs] = useState<Workspace | null>(null),
    [page, setPage] = useState("overview"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [role, setRole] = useState("reviewer"),
    [password, setPassword] = useState(""),
    [checking, setChecking] = useState(true);
  useEffect(() => {
    api("/config")
      .then((config) => {
        setAuthConfig(config);
        setRole((previous) =>
          previous === "member" || config.roles.includes(previous)
            ? previous
            : "member",
        );
      })
      .catch(() => {});
  }, []);
  const [selected, setSelected] = useState<Claim | null>(null),
    [evidence, setEvidence] = useState<Evidence[]>([]),
    [edit, setEdit] = useState(""),
    [owner, setOwner] = useState("");
  const [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [importOpen, setImportOpen] = useState(false);
  const [sourceName, setSourceName] = useState(""),
    [sourceText, setSourceText] = useState(""),
    [kind, setKind] = useState("notes"),
    [access, setAccess] = useState("core"),
    [authorised, setAuthorised] = useState(false),
    [repo, setRepo] = useState("");
  const [question, setQuestion] = useState(""),
    [answers, setAnswers] = useState<Claim[]>([]),
    [answerText, setAnswerText] = useState(""),
    [versionView, setVersionView] = useState<{
      number: number;
      claims: Claim[];
      removed_count: number;
    } | null>(null);
  const load = async () => {
    const data = await api("/workspace");
    setWs(data);
    return data;
  };
  useEffect(() => {
    load()
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [page]);
  useEffect(() => {
    if (!selected && !importOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    const focusable = () =>
      Array.from(
        dialog?.querySelectorAll<HTMLElement>(
          "button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]",
        ) || [],
      );
    focusable()[0]?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSelected(null);
        setImportOpen(false);
      }
      if (event.key === "Tab") {
        const elements = focusable(),
          first = elements[0],
          last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [selected?.id, importOpen]);
  async function act(fn: () => Promise<unknown>, message = "") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await load();
      if (message) setNotice(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function inspect(c: Claim) {
    setSelected(c);
    setEdit(c.status === "gap" ? "" : c.text);
    setOwner(c.owner);
    setEvidence([]);
    try {
      const version =
        page === "history"
          ? versionView?.number
          : page === "handover"
            ? ws?.versions.length
            : undefined;
      setEvidence(
        await api("/evidence/" + c.id + (version ? "?version=" + version : "")),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const reviewer = ws?.user.role === "reviewer";
  const claims = ws?.claims || [],
    accessible = claims.filter((c) => !c.restricted),
    pending = accessible.filter((c) => c.review === "pending");
  const conflicts = accessible.filter(
      (c) => c.status === "conflicting" && c.review !== "rejected",
    ),
    gaps = accessible.filter(
      (c) => c.status === "gap" && c.review !== "rejected",
    );
  const supported = accessible.filter(
    (c) =>
      ["verified", "attested"].includes(c.status || "") &&
      c.review !== "rejected",
  );
  const handoverAccessible = (ws?.approved_claims || []).filter(
    (c) => !c.restricted,
  );
  const shown = claims.filter(
    (c) =>
      (filter === "all" || c.status === filter || c.review === filter) &&
      (!query || c.text.toLowerCase().includes(query.toLowerCase())),
  );
  const rank = (c: Claim) =>
    c.type === "risk"
      ? 0
      : c.type === "dependency"
        ? 1
        : c.owner === "Unassigned"
          ? 2
          : 3;
  const nextActions = (page === "handover" ? handoverAccessible : accessible)
    .filter(
      (c) =>
        c.review !== "rejected" &&
        ["risk", "dependency", "work", "question"].includes(c.type || ""),
    )
    .sort((a, b) => rank(a) - rank(b));
  async function review(c: Claim, action: string, text?: string) {
    await act(
      () =>
        api("/claims/" + c.id, "PATCH", { action, text: text || "", owner }),
      action === "attest"
        ? "Answer saved with your name and timestamp."
        : "Review saved.",
    );
    setSelected(null);
  }
  function card(c: Claim, compact = false) {
    return (
      <article
        className={"claim " + (c.restricted ? "restricted" : "")}
        key={c.id}
      >
        {c.restricted ? (
          <>
            <LockKeyhole size={19} />
            <h3>Restricted knowledge</h3>
            <p>A source requires additional permission. Ask {c.owner}.</p>
          </>
        ) : (
          <>
            <div className="claim-top">
              <span className="eyebrow">{c.type}</span>
              <Badge value={c.status} />
            </div>
            <button className="claim-title" onClick={() => inspect(c)}>
              {c.text}
            </button>
            {!compact && <p className="claim-reason">{c.reason}</p>}
            <div className="claim-bottom">
              <span>
                <span className="avatar tiny">{c.owner[0]}</span>
                {c.owner}
              </span>
              <button className="text-button" onClick={() => inspect(c)}>
                View receipt <ArrowUpRight size={14} />
              </button>
            </div>
            <div className="claim-tags">
              {c.review && (
                <span>
                  {c.review === "approved" ? <Check size={12} /> : null}
                  {c.review}
                </span>
              )}
              {c.stale && <span>Older than 60 days</span>}
              {c.attestation && <span>Attested by {c.attestation.by}</span>}
              {c.change && <span>{c.change}</span>}
            </div>
          </>
        )}
      </article>
    );
  }
  if (checking) return <div className="loading">Opening your workspace…</div>;
  if (!ws && joining)
    return (
      <JoinWorkspace
        api={api}
        onBack={() => setJoining(false)}
        onJoined={(username) => {
          setUsername(username);
          setRole("member");
          setJoining(false);
          setNotice(
            "Account created. Sign in with your username and password.",
          );
        }}
      />
    );
  if (!ws)
    return (
      <main className="login-page">
        <div className="login-story">
          <div className="brand">
            <span className="logo-symbol"><img src="/assets/images/baton-logo.png" alt="" /></span>baton
          </div>
          <span className="eyebrow">Knowledge moves forward</span>
          <h1>
            People move on.
            <br />
            Understanding
            <br />
            <em>should stay.</em>
          </h1>
          <p>
            Turn scattered project activity into a handover that shows its
            receipts.
          </p>
          <div className="login-proof">
            <ShieldCheck />
            <span>Evidence linked. Human reviewed. Permission aware.</span>
          </div>
          <div className="orbit">
            <span>Connect</span>
            <ArrowRight />
            <span>Reconstruct</span>
            <ArrowRight />
            <span>Review</span>
            <ArrowRight />
            <span>Handover</span>
          </div>
        </div>
        <div className="login-form">
          <span className="badge verified">Round 2 · working build</span>
          <h2>Pick up the baton.</h2>
          <p>Sign in to the project workspace.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                await api("/login", "POST", {
                  role: role === "member" ? "reviewer" : role,
                  username: role === "member" ? username : "",
                  password,
                });
                setPassword("");
              });
            }}
          >
            <label>
              Your role
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {authConfig.roles.includes("reviewer") && (
                  <option value="reviewer">Kabir · Reviewer</option>
                )}
                {authConfig.roles.includes("successor") && (
                  <option value="successor">Meera · Technical successor</option>
                )}
                {authConfig.roles.includes("coordinator") && (
                  <option value="coordinator">Riya · Coordinator</option>
                )}
                {authConfig.roles.includes("leaver") && (
                  <option value="leaver">Aarav · Departing member</option>
                )}
                <option value="member">My named account</option>
              </select>
            </label>
            {role === "member" && (
              <label>
                Username
                <input
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                />
              </label>
            )}
            <label>
              Password
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            {error && (
              <div className="error" role="alert">
                {error}
              </div>
            )}
            <button className="primary full" disabled={busy}>
              {busy ? "Signing in…" : "Open workspace"}
              <ArrowRight size={17} />
            </button>
          </form>
          {notice && (
            <div className="success" role="status">
              {notice}
            </div>
          )}
          <div className="login-extra">
            <button className="text-button" onClick={() => setJoining(true)}>
              Join with invitation
            </button>
          </div>
          <div className="demo-note">
            <strong>
              {authConfig.demo
                ? "Synthetic demonstration accounts"
                : "Private project access"}
            </strong>
            {authConfig.demo ? (
              <p>
                Demo password: <code>baton-demo-2026</code>. Use synthetic or
                public data only in a shared demonstration.
              </p>
            ) : (
              <p>
                Use your private reviewer credentials or a named account. New
                team members need an invitation from the reviewer.
              </p>
            )}
          </div>
        </div>
      </main>
    );
  return (
    <div className="app-shell">
      <header className="workspace-header">
        <a className="brand" href="#" onClick={() => setPage("overview")}>
          <span className="logo-symbol"><img src="/assets/images/baton-logo.png" alt="" /></span>baton
        </a>

        <div className="project-picker">
          <span className="project-icon">F</span>
          <span>
            Fest registration<small>Project handover</small>
          </span>
          <ChevronRight size={15} />
        </div>

        <nav className="workspace-nav" aria-label="Workspace navigation">
          {nav
            .filter((item) => item.id !== "people" || reviewer)
            .map((item) => (
              <button
                key={item.id}
                className={page === item.id ? "nav-item active" : "nav-item"}
                aria-label={item.label}
                aria-current={page === item.id ? "page" : undefined}
                title={item.label}
                onClick={() => {
                  setPage(item.id);
                  setQuery("");
                  setFilter("all");
                  setVersionView(null);
                }}
              >
                <item.icon size={18} />
                {item.label}
                {item.id === "questions" && gaps.length > 0 ? (
                  <span className="nav-count">{gaps.length}</span>
                ) : null}
              </button>
            ))}
        </nav>
        <div className="user-block">
          <span className="avatar">{ws.user.name[0]}</span>
          <span>
            {ws.user.name}
            <small>{ws.user.role}</small>
          </span>
          <button
            aria-label="Sign out"
            onClick={() =>
              act(async () => {
                await api("/logout", "POST");
                setWs(null);
                window.location.reload();
              })
            }
          >
            <LogOut size={16} />
          </button>
        </div>
      </header>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} /> Fest registration{" "}
            <ChevronRight size={13} />
            <strong>{nav.find((n) => n.id === page)?.label}</strong>
          </div>
          <div className="topbar-right">
            <span className="live-dot" />{" "}
            {ws.versions.length
              ? "Version " + ws.versions.length + " published"
              : "Draft workspace"}
            <span className="avatar small">{ws.user.name[0]}</span>
          </div>
        </header>
        <main className="content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                FEST REGISTRATION PORTAL{" "}
                <span className="muted">/ HANDOVER 001</span>
              </span>
              <h1>
                {page === "overview"
                  ? "The work continues."
                  : nav.find((n) => n.id === page)?.label}
              </h1>
              <p>
                {page === "overview"
                  ? "The project, the context, and the loose ends. All in one place."
                  : page === "sources"
                    ? "Bring the project’s knowledge together. Set access at the source."
                    : page === "review"
                      ? "Inspect the evidence. Resolve uncertainty. Approve what you trust."
                      : page === "handover"
                        ? "A continuation plan built from the knowledge you can access."
                        : page === "questions"
                          ? "Small questions that close the biggest knowledge gaps."
                          : "Follow the decisions, people, and changes behind the work."}
              </p>
            </div>
            {reviewer && (
              <button
                className="primary"
                disabled={busy}
                onClick={() => {
                  setImportOpen(true);
                  setPage("sources");
                }}
              >
                <Plus size={17} /> Add source
              </button>
            )}
          </div>
          {(error || notice) && (
            <div
              className={error ? "error" : "success"}
              role={error ? "alert" : "status"}
            >
              {error || notice}
              <button
                aria-label="Dismiss message"
                onClick={() => {
                  setError("");
                  setNotice("");
                }}
              >
                <X size={15} />
              </button>
            </div>
          )}
          {busy && (
            <div className="busy-bar" role="status">
              Working… please keep this window open.
            </div>
          )}
          {page === "overview" && (
            <>
              <section className="handover-banner">
                <div>
                  <span className="eyebrow">
                    A HANDOVER THAT SHOWS ITS RECEIPTS
                  </span>
                  <h2>
                    People move on.
                    <br />
                    Context stays.
                  </h2>
                  <p>
                    Aarav is passing the baton to Meera.
                    <br />
                    Let’s make sure nothing important gets left behind.
                  </p>
                  <button
                    className="light-button"
                    onClick={() => setPage(reviewer ? "review" : "handover")}
                  >
                    {reviewer ? "Open review workspace" : "Open your handover"}
                    <ArrowUpRight size={16} />
                  </button>
                </div>
                <figure className="hero-image">
                  <img src="/assets/images/architecture.jpg" alt="Monochrome concrete stairs rising through an angular architectural space" fetchPriority="high" />
                  <figcaption>Context is the next step. <a href="https://unsplash.com/photos/b5YlVPjRH3A" target="_blank" rel="noreferrer">Photo: Mauro Lima</a></figcaption>
                </figure>
              </section>
              <div className="stats">
                <div>
                  <span className="stat-label">
                    Connected sources <Files size={16} />
                  </span>
                  <strong>
                    {ws.sources.length.toString().padStart(2, "0")}
                  </strong>
                  <small>Notes, tasks, git & conversations</small>
                </div>
                <div>
                  <span className="stat-label">
                    Supported claims <ShieldCheck size={16} />
                  </span>
                  <strong>
                    {supported.length.toString().padStart(2, "0")}
                    <span className="stat-pill">with receipts</span>
                  </strong>
                  <small>Quote verified or human attested</small>
                </div>
                <div>
                  <span className="stat-label">
                    Needs attention <AlertTriangle size={16} />
                  </span>
                  <strong>
                    {(conflicts.length + gaps.length)
                      .toString()
                      .padStart(2, "0")}
                    <span className="attention-dot" />
                  </strong>
                  <small>
                    {conflicts.length} conflicting · {gaps.length} missing
                    context
                  </small>
                </div>
                <div>
                  <span className="stat-label">
                    Review progress <CheckCheck size={16} />
                  </span>
                  <strong>
                    {accessible.length
                      ? Math.round(
                          ((accessible.length - pending.length) /
                            accessible.length) *
                            100,
                        )
                      : 0}
                    <span className="percent">%</span>
                  </strong>
                  <small>{pending.length} claims still need a decision</small>
                </div>
              </div>
              <div className="overview-columns">
                <section>
                  <div className="section-heading">
                    <h2>Your handover, step by step</h2>
                    <span className="muted">THE WORKFLOW</span>
                  </div>
                  <div className="steps">
                    {[
                      {
                        title: "Connect the dots",
                        text: "Add authorised project sources.",
                        done: ws.sources.length > 0,
                        target: "sources",
                      },
                      {
                        title: "Reconstruct & verify",
                        text: "Turn activity into evidence-linked claims.",
                        done: claims.length > 0,
                        target: "review",
                      },
                      {
                        title: "Review with a human",
                        text: "Resolve conflicts and close the gaps.",
                        done: claims.length > 0 && pending.length === 0,
                        target: "review",
                      },
                      {
                        title: "Pass the baton",
                        text: "Publish an approved, role-aware handover.",
                        done: ws.versions.length > 0,
                        target: "handover",
                      },
                    ].map((x, i) => (
                      <button
                        className="step"
                        key={x.title}
                        onClick={() => setPage(x.target)}
                      >
                        <span
                          className={
                            x.done ? "step-number done" : "step-number"
                          }
                        >
                          {x.done ? <Check size={17} /> : i + 1}
                        </span>
                        <span>
                          <strong>{x.title}</strong>
                          <small>{x.text}</small>
                        </span>
                        <ChevronRight size={17} />
                      </button>
                    ))}
                  </div>
                </section>
                <section className="attention-panel">
                  <div className="section-heading">
                    <h2>Worth a closer look</h2>
                    <span className="orange-dot" />
                  </div>
                  {conflicts
                    .concat(gaps)
                    .slice(0, 2)
                    .map((c) => (
                      <button
                        className="attention-item"
                        key={c.id}
                        onClick={() => inspect(c)}
                      >
                        <Badge value={c.status} />
                        <strong>{c.text}</strong>
                        <span>
                          Review the evidence <ArrowUpRight size={14} />
                        </span>
                      </button>
                    ))}
                  {!conflicts.length && !gaps.length && (
                    <div className="quiet-state">
                      <ShieldCheck size={29} />
                      <h3>
                        {claims.length
                          ? "No unresolved flags"
                          : "Start with the sources"}
                      </h3>
                      <p>
                        {claims.length
                          ? "Keep reviewing the ledger before publishing."
                          : "Load the synthetic demo or import your own authorised project."}
                      </p>
                      {reviewer && !ws.sources.length && (
                        <button
                          className="text-button"
                          disabled={busy}
                          onClick={() =>
                            act(
                              () => api("/demo", "POST"),
                              "Synthetic demo loaded. Reconstruct to discover the project.",
                            )
                          }
                        >
                          Load demo project <ArrowRight size={15} />
                        </button>
                      )}
                    </div>
                  )}
                </section>
              </div>
              <section className="mode-note">
                <ShieldCheck size={17} />
                <span>
                  <strong>Trust is part of the workflow.</strong> Nothing is
                  shared until the reviewer publishes it. Restricted evidence
                  stays restricted.
                </span>
              </section>
            </>
          )}
          {page === "sources" && (
            <>
              <div className="toolbar">
                <span>
                  {ws.sources.length} connected sources ·{" "}
                  {ws.sources.reduce((n, s) => n + s.redactions, 0)} redactions
                </span>
                <div>
                  {reviewer && !ws.sources.length && (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() =>
                        act(
                          () => api("/demo", "POST"),
                          "Synthetic demo loaded.",
                        )
                      }
                    >
                      Load synthetic demo
                    </button>
                  )}
                  {reviewer && (
                    <button
                      className="primary"
                      disabled={busy || !ws.sources.length}
                      onClick={() =>
                        act(
                          () => api("/reconstruct", "POST"),
                          "Project reconstructed. Open the claim ledger to review.",
                        )
                      }
                    >
                      <RefreshCw size={16} />
                      Reconstruct project
                    </button>
                  )}
                </div>
              </div>
              <div className="source-grid">
                {ws.sources.map((s) => (
                  <article className="source-card" key={s.id}>
                    <div className="source-icon">
                      {s.kind === "git" ? <GitBranch /> : <FileText />}
                    </div>
                    <Badge value={s.kind} />
                    <h3>{s.name}</h3>
                    <p>
                      {s.lines} lines · {s.redactions} sensitive matches masked
                    </p>
                    {reviewer ? (
                      <label>
                        Source access
                        <select
                          aria-label={"Access for " + s.name}
                          value={s.access}
                          disabled={busy}
                          onChange={(e) =>
                            act(
                              () =>
                                api("/sources/" + s.id, "PATCH", {
                                  access: e.target.value,
                                }),
                              "Access updated. Existing views are filtered on their next request.",
                            )
                          }
                        >
                          <option value="core">Core team</option>
                          <option value="technical">Technical only</option>
                          <option value="leads">Leads only</option>
                        </select>
                      </label>
                    ) : (
                      <Badge value={s.access} />
                    )}
                    <small>
                      Content is hashed and redacted before extraction.
                    </small>
                    {reviewer && (
                      <button
                        className="text-button danger"
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              "Remove this source? Its claims will lose access to their evidence.",
                            )
                          )
                            act(
                              () => api("/sources/" + s.id, "DELETE"),
                              "Source removed. Dependent claims need review.",
                            );
                        }}
                      >
                        Remove source
                      </button>
                    )}
                  </article>
                ))}
                {reviewer && (
                  <button
                    className="add-source-card"
                    onClick={() => setImportOpen(true)}
                  >
                    <Plus size={27} />
                    <strong>Connect a source</strong>
                    <span>Notes, chat, tasks or a public repo</span>
                  </button>
                )}
              </div>
            </>
          )}
          {page === "review" && (
            <>
              <div className="toolbar">
                <div className="search">
                  <Search size={17} />
                  <input
                    aria-label="Search claims"
                    placeholder="Search the ledger…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>
                <div>
                  <span className="mode-label">{ws.mode}</span>
                  {reviewer && (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() =>
                        act(
                          () => api("/approve-verified", "POST"),
                          "Supported claims approved. Resolve or reject the remaining claims.",
                        )
                      }
                    >
                      <CheckCheck size={16} />
                      Approve supported
                    </button>
                  )}
                </div>
              </div>
              <div className="filter-tabs">
                {[
                  "all",
                  "pending",
                  "verified",
                  "attested",
                  "conflicting",
                  "gap",
                  "inferred",
                  "rejected",
                ].map((f) => (
                  <button
                    key={f}
                    className={filter === f ? "selected" : ""}
                    onClick={() => setFilter(f)}
                  >
                    {f === "all" ? "All claims" : f}
                  </button>
                ))}
              </div>
              <div className="claim-grid">{shown.map((c) => card(c))}</div>
              {!shown.length && (
                <div className="empty">
                  <ShieldCheck />
                  <h2>
                    {claims.length
                      ? "No matching claims"
                      : "Your ledger is ready for its first receipts."}
                  </h2>
                  <p>Import sources, then reconstruct the project.</p>
                  <button
                    className="secondary"
                    onClick={() => setPage("sources")}
                  >
                    Go to sources
                    <ArrowRight size={16} />
                  </button>
                </div>
              )}
            </>
          )}
          {page === "questions" && (
            <>
              <div className="callout">
                <CircleHelp />
                <div>
                  <strong>
                    {ws.sudden_exit
                      ? "Sudden-exit mode · Ask the reviewer or teammates"
                      : "Planned exit · Ask Aarav before the handover"}
                  </strong>
                  <p>
                    Answers become named attestations. They still need reviewer
                    approval.
                  </p>
                </div>
                {reviewer && (
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      act(() =>
                        api("/settings", "PATCH", {
                          sudden_exit: !ws.sudden_exit,
                        }),
                      )
                    }
                  >
                    {ws.sudden_exit ? "Use planned exit" : "Use sudden exit"}
                  </button>
                )}
              </div>
              <QuestionQueue
                claims={gaps}
                assignments={ws.questions || []}
                api={api}
                act={act}
                busy={busy}
                reviewer={reviewer}
                sudden={ws.sudden_exit}
                onInspect={inspect}
              />
              {!gaps.length && (
                <div className="empty">
                  <CheckCheck />
                  <h2>No open gap questions</h2>
                  <p>Reconstruct your sources to identify missing context.</p>
                </div>
              )}
            </>
          )}
          {page === "timeline" && (
            <div className="timeline">
              {[...accessible]
                .filter((c) => c.review !== "rejected")
                .sort((a, b) => (b.date || "").localeCompare(a.date || ""))
                .map((c) => (
                  <div className="timeline-entry" key={c.id}>
                    <time>{c.date}</time>
                    <span className="timeline-dot" />
                    <div>{card(c, true)}</div>
                  </div>
                ))}
              {!accessible.length && (
                <div className="empty">No project activity to show yet.</div>
              )}
            </div>
          )}
          {page === "ownership" && (
            <>
              <div className="callout">
                <Users />
                <div>
                  <strong>
                    Ownership signal, not a definitive bus factor.
                  </strong>
                  <p>
                    Derived from explicit owners in the ledger. A single named
                    owner suggests concentration; it does not prove exclusive
                    knowledge.
                  </p>
                </div>
              </div>
              <div className="source-grid">
                {Array.from(new Set(accessible.map((c) => c.owner))).map(
                  (name) => {
                    const owned = accessible.filter(
                      (c) => c.owner === name && c.review !== "rejected",
                    );
                    return (
                      <article className="source-card" key={name}>
                        <span className="avatar">{name[0]}</span>
                        <h3>{name}</h3>
                        <p>
                          {owned.length} claim{owned.length !== 1 ? "s" : ""} ·{" "}
                          {owned.filter((c) => c.type === "risk").length} risks
                        </p>
                        {name === "Aarav" ? <Badge value="gap" /> : null}
                        {owned.slice(0, 4).map((c) => (
                          <button
                            key={c.id}
                            className="ownership-link"
                            onClick={() => inspect(c)}
                          >
                            {c.text}
                            <ArrowUpRight size={14} />
                          </button>
                        ))}
                      </article>
                    );
                  },
                )}
              </div>
            </>
          )}
          {page === "handover" && (
            <>
              <div className="publish-panel">
                <div>
                  <span className="eyebrow">THE APPROVAL GATE</span>
                  <h2>
                    {ws.versions.length
                      ? "Version " + ws.versions.length + " is published."
                      : "Ready when you’ve reviewed it."}
                  </h2>
                  <p>
                    {reviewer
                      ? `${pending.length} pending claims. Resolve or reject uncertainty before publishing.`
                      : "Your view contains only approved claims and accessible evidence."}
                  </p>
                </div>
                {reviewer && (
                  <button
                    className="primary"
                    disabled={busy || !claims.length || pending.length > 0}
                    onClick={() =>
                      act(
                        () => api("/publish", "POST"),
                        "Approved handover published. Successors can now open it.",
                      )
                    }
                  >
                    <Send size={16} />
                    Publish handover
                  </button>
                )}
              </div>
              {ws.versions.length > 0 && (
                <>
                  <ActionBoard
                    actions={ws.actions || []}
                    claims={ws.approved_claims || []}
                    api={api}
                    act={act}
                    busy={busy}
                    reviewer={reviewer}
                    name={ws.user.name}
                    onInspect={inspect}
                  />
                  {ws.receipt_stale && (
                    <div className="callout">
                      <AlertTriangle size={19} />
                      <span>
                        Your previous acknowledgement is out of date. Access or
                        continuation actions changed; review the current
                        handover and acknowledge again.
                      </span>
                    </div>
                  )}
                  <div className="toolbar">
                    <span>
                      Downloads reflect your current access. Downloaded files
                      cannot be revoked.
                    </span>
                    <div>
                      <a className="secondary" href="/api/export/md">
                        <Download size={16} />
                        Markdown
                      </a>
                      <a className="secondary" href="/api/export/pdf">
                        <Download size={16} />
                        PDF
                      </a>
                    </div>
                  </div>
                  {reviewer && (
                    <div className="callout">
                      The continuation workspace uses the latest approved
                      snapshot. Review draft changes in the claim ledger before
                      publishing another version.
                    </div>
                  )}
                  <div className="plan-grid">
                    {["Day 1", "Week 1", "Day 30"].map((day, i) => (
                      <section className="plan-column" key={day}>
                        <span className="eyebrow">{day}</span>
                        <h2>
                          {
                            [
                              "Remove the blockers",
                              "Build the context",
                              "Strengthen continuity",
                            ][i]
                          }
                        </h2>
                        <p>
                          {
                            [
                              "Start with risks and dependencies.",
                              "Understand decisions and ownership.",
                              "Confirm responsibility and capture what changed.",
                            ][i]
                          }
                        </p>
                        {(i === 0
                          ? nextActions.slice(0, 4)
                          : i === 1
                            ? handoverAccessible
                                .filter(
                                  (c) =>
                                    c.type === "decision" &&
                                    c.review !== "rejected",
                                )
                                .slice(0, 4)
                            : handoverAccessible
                                .filter(
                                  (c) =>
                                    ["recurring", "contact", "work"].includes(
                                      c.type || "",
                                    ) && c.review !== "rejected",
                                )
                                .slice(0, 4)
                        ).map((c) => (
                          <button
                            className="plan-item"
                            key={c.id}
                            onClick={() => inspect(c)}
                          >
                            <span className="checkbox" />
                            <span>
                              {c.text}
                              <small>Confirm next step with {c.owner}</small>
                            </span>
                          </button>
                        ))}
                      </section>
                    ))}
                  </div>
                  <div className="section-heading">
                    <h2>Acknowledge your handover</h2>
                    <span className="muted">Version {ws.versions.length}</span>
                  </div>
                  <p className="muted">
                    Read the current version before acknowledging. Access
                    changes require another review.
                  </p>
                  <div className="ack-grid">
                    {["decisions", "risks", "next actions"].map((section) => {
                      const ack = ws.acks.find(
                        (a) =>
                          a.section === section &&
                          (a.user_id || a.role) === ws.user.id &&
                          a.version === ws.versions.length,
                      );
                      return (
                        <button
                          className={"ack " + (ack ? "acknowledged" : "")}
                          key={section}
                          disabled={busy}
                          onClick={() =>
                            act(
                              () => api("/acknowledge", "POST", { section }),
                              "Receipt recorded for this version.",
                            )
                          }
                        >
                          <CheckCheck size={20} />
                          <span>
                            {section}
                            <small>
                              {ack
                                ? "Received by " + ack.by
                                : "Mark as received"}
                            </small>
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <section className="qa-panel">
                    <h2>Find an answer in the approved ledger</h2>
                    <p>
                      Evidence search returns authorised claims verbatim. It
                      will say when no answer is available.
                    </p>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        act(async () => {
                          const r = await api("/ask", "POST", { question });
                          setAnswers(r.claims);
                          setAnswerText(r.answer);
                        });
                      }}
                      className="qa-form"
                    >
                      <input
                        aria-label="Question about the handover"
                        placeholder="What is blocking payments?"
                        required
                        minLength={3}
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                      />
                      <button className="primary" disabled={busy}>
                        Find evidence
                        <ArrowRight size={16} />
                      </button>
                    </form>
                    {answerText && <p role="status">{answerText}</p>}
                    <div className="claim-grid">
                      {answers.map((c) => card(c, true))}
                    </div>
                  </section>
                </>
              )}
            </>
          )}
          {page === "history" && (
            <>
              <div className="section-heading">
                <h2>Approved versions</h2>
                <span className="muted">
                  Immutable content · live access checks
                </span>
              </div>
              <div className="versions">
                {ws.versions.map((v) => (
                  <button
                    key={v.number}
                    onClick={() =>
                      act(async () =>
                        setVersionView(await api("/versions/" + v.number)),
                      )
                    }
                  >
                    <GitBranch />
                    <strong>Version {v.number}</strong>
                    <span>{new Date(v.at).toLocaleString()}</span>
                    <span>
                      {v.count} claims · {v.by}
                    </span>
                    <ArrowUpRight size={16} />
                  </button>
                ))}
              </div>
              {versionView && (
                <section>
                  <div className="section-heading">
                    <h2>
                      Version {versionView.number} · changes from previous
                    </h2>
                    <span>
                      {versionView.removed_count} accessible claims removed
                    </span>
                  </div>
                  <div className="claim-grid">
                    {versionView.claims.map((c) => (
                      <div key={c.id}>
                        {card(c, true)}
                        {c.change === "changed" && (
                          <div className="version-change">
                            <strong>
                              Changed: {c.changed_fields?.join(", ")}
                            </strong>
                            {Object.entries(c.previous || {}).map(
                              ([field, value]) => (
                                <p key={field}>
                                  {field} previously:{" "}
                                  {typeof value === "object"
                                    ? JSON.stringify(value)
                                    : String(value)}
                                </p>
                              ),
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}
              {reviewer && (
                <>
                  <div className="section-heading">
                    <h2>Activity log</h2>
                    <span className="muted">Server-recorded actions</span>
                  </div>
                  <div className="activity">
                    {ws.audit.map((a, i) => (
                      <div key={i}>
                        <span className="activity-dot" />
                        <strong>{a.action}</strong>
                        <span>{a.detail}</span>
                        <small>
                          {a.actor} · {new Date(a.at).toLocaleString()}
                        </small>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
          {page === "people" && reviewer && (
            <TeamPanel api={api} act={act} busy={busy} />
          )}
          <footer>
            <span>
              baton.{" "}
              <span className="muted">A handover that shows its receipts.</span>
            </span>
            <span>
              <span className="live-dot" />
              {ws.demo
                ? "Synthetic demo workspace"
                : "Private project workspace"}
            </span>
          </footer>
        </main>
      </div>
      {selected && (
        <div className="modal-backdrop" onClick={() => setSelected(null)}>
          <section
            className="evidence-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Claim evidence"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="drawer-heading">
              <span className="eyebrow">THE RECEIPT</span>
              <button
                aria-label="Close evidence"
                onClick={() => setSelected(null)}
              >
                <X />
              </button>
            </div>
            <Badge value={selected.status} />
            <h2>{selected.text}</h2>
            <p>{selected.reason}</p>
            {selected.attestation && (
              <div className="callout">
                Attested by {selected.attestation.by} ·{" "}
                {new Date(selected.attestation.at).toLocaleString()}
              </div>
            )}
            <h3>Supporting evidence</h3>
            {evidence.map((e, i) => (
              <div className="receipt" key={i}>
                <div>
                  <FileText size={15} />
                  <strong>{e.source}</strong>
                </div>
                <small>
                  {e.locator} ·{" "}
                  {e.found ? "Exact quote found" : "Quote not found"}
                </small>
                <blockquote>{e.quote}</blockquote>
              </div>
            ))}
            {selected.conflicts?.length ? (
              <div className="conflict-notice">
                <AlertTriangle size={18} />
                <div>
                  <strong>Conflicting evidence</strong>
                  {selected.conflicts.map((id) => {
                    const peer = claims.find((c) => c.id === id);
                    return peer ? (
                      <button
                        className="ownership-link"
                        key={id}
                        onClick={() => inspect(peer)}
                      >
                        {peer.text}
                        <ArrowUpRight size={14} />
                      </button>
                    ) : null;
                  })}
                </div>
              </div>
            ) : null}
            {((reviewer && page !== "history" && page !== "handover") ||
              (ws.user.role === "leaver" &&
                selected.status === "gap" &&
                !ws.sudden_exit)) && (
              <div className="edit-form">
                <h3>
                  {selected.status === "gap"
                    ? "Fill the knowledge gap"
                    : "Correct or attest this claim"}
                </h3>
                <label>
                  {selected.status === "gap" ? "Your answer" : "Claim text"}
                  <textarea
                    rows={4}
                    value={edit}
                    onChange={(e) => setEdit(e.target.value)}
                  />
                </label>
                <label>
                  Owner
                  <input
                    value={owner}
                    onChange={(e) => setOwner(e.target.value)}
                  />
                </label>
                <button
                  className="secondary full"
                  disabled={busy || !edit.trim()}
                  onClick={() => review(selected, "attest", edit)}
                >
                  Save named attestation
                </button>
                <p className="muted">
                  Signed as {ws.user.name}. Human answers remain pending until
                  approved.
                </p>
              </div>
            )}
            {reviewer && page !== "history" && page !== "handover" && (
              <div className="review-actions">
                <button
                  className="secondary danger"
                  disabled={busy}
                  onClick={() => review(selected, "reject")}
                >
                  <X size={16} />
                  Reject
                </button>
                <button
                  className="primary"
                  disabled={
                    busy ||
                    !["verified", "attested"].includes(selected.status || "")
                  }
                  onClick={() => review(selected, "approve")}
                >
                  <Check size={16} />
                  Approve claim
                </button>
              </div>
            )}
          </section>
        </div>
      )}
      {importOpen && (
        <div className="modal-backdrop" onClick={() => setImportOpen(false)}>
          <section
            className="import-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Import authorised source"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="drawer-heading">
              <span className="eyebrow">CONNECT THE DOTS</span>
              <button
                aria-label="Close import"
                onClick={() => setImportOpen(false)}
              >
                <X />
              </button>
            </div>
            <h2>Add an authorised source</h2>
            <p>
              Plain text, Markdown, CSV, JSON, chat exports, or a public GitHub
              repository.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                act(async () => {
                  if (repo)
                    await api("/github", "POST", {
                      url: repo,
                      access,
                      authorised,
                    });
                  else
                    await api("/sources", "POST", {
                      name: sourceName,
                      kind,
                      access,
                      text: sourceText,
                      authorised,
                    });
                  setImportOpen(false);
                  setSourceName("");
                  setSourceText("");
                  setRepo("");
                  setAuthorised(false);
                }, "Source imported. Reconstruct when your sources are ready.");
              }}
            >
              <label>
                Public GitHub URL (optional)
                <input
                  placeholder="https://github.com/owner/project"
                  value={repo}
                  onChange={(e) => setRepo(e.target.value)}
                />
              </label>
              {!repo && (
                <>
                  <label>
                    Upload a text export
                    <input
                      type="file"
                      accept=".md,.txt,.csv,.json,.log"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          if (file.size > 250000) {
                            setError("Choose a file under 250 KB.");
                            return;
                          }
                          setSourceName(file.name);
                          setSourceText(await file.text());
                          if (file.name.endsWith(".csv")) setKind("tasks");
                        }
                      }}
                    />
                  </label>
                  <label>
                    Source name
                    <input
                      required
                      value={sourceName}
                      placeholder="meeting-notes.md"
                      onChange={(e) => setSourceName(e.target.value)}
                    />
                  </label>
                  <label>
                    Paste source content
                    <textarea
                      required
                      rows={5}
                      value={sourceText}
                      maxLength={250000}
                      onChange={(e) => setSourceText(e.target.value)}
                      placeholder="Decisions, owners, risks and next steps…"
                    />
                  </label>
                  <label>
                    Source type
                    <select
                      value={kind}
                      onChange={(e) => setKind(e.target.value)}
                    >
                      <option value="notes">Notes & documents</option>
                      <option value="tasks">Task board export</option>
                      <option value="chat">Chat export</option>
                      <option value="git">Git history export</option>
                    </select>
                  </label>
                </>
              )}
              <label>
                Who may see this source?
                <select
                  value={access}
                  onChange={(e) => setAccess(e.target.value)}
                >
                  <option value="core">Core team · all project roles</option>
                  <option value="technical">
                    Technical · reviewer, successor & leaver
                  </option>
                  <option value="leads">Leads only · reviewer</option>
                </select>
              </label>
              <label className="check-label">
                <input
                  type="checkbox"
                  required
                  checked={authorised}
                  onChange={(e) => setAuthorised(e.target.checked)}
                />
                I am authorised to import this data. Demo sources are synthetic,
                public, permissioned or anonymised.
              </label>
              <button className="primary full" disabled={busy || !authorised}>
                {busy ? "Importing…" : "Import source"}
                <ArrowRight size={17} />
              </button>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
