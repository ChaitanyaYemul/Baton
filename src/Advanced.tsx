import { useEffect, useState } from "react";
import { Plus, CheckCheck, ArrowUpRight, UserPlus } from "lucide-react";
import "./advanced.css";
import { EvidenceDisclosure } from "./Round3";

type Claim = {
  id: string;
  text: string;
  owner: string;
  reason: string;
  status?: string;
  restricted?: boolean;
};
export type Action = {
  id: string;
  claim_id: string;
  version: number;
  title: string;
  owner: string;
  phase: "Day 1" | "Week 1" | "Day 30";
  due: string | null;
  status: "todo" | "in_progress" | "blocked" | "done";
  updated_at: string;
};
export type Assignment = {
  id: string;
  claim_id: string;
  assignee: "reviewer" | "leaver";
  assignee_id?: string;
  assignee_name?: string;
  prompt: string;
  answer_hint?: string;
  claim_status: string;
  claim_review: string;
  can_answer: boolean;
  can_confirm: boolean;
  answers: { text: string; by: string; at: string; follow_up: string | null }[];
  priority: "high" | "medium" | "low";
  due: string | null;
  answered_at?: string;
};
type Api = (path: string, method?: string, data?: unknown) => Promise<any>;
type Act = (fn: () => Promise<unknown>, message?: string) => Promise<void>;
type Shared = { api: Api; act: Act; busy: boolean; reviewer: boolean };

export function ActionBoard({
  actions,
  claims,
  api,
  act,
  busy,
  reviewer,
  onInspect,
  name,
}: {
  actions: Action[];
  claims: Claim[];
  onInspect: (claim: Claim) => void;
  name: string;
} & Shared) {
  const [adding, setAdding] = useState(false);
  const [claimId, setClaimId] = useState(""),
    [title, setTitle] = useState(""),
    [owner, setOwner] = useState("Meera"),
    [phase, setPhase] = useState<Action["phase"]>("Day 1"),
    [due, setDue] = useState("");
  return (
    <section className="advanced-section">
      <div className="section-heading">
        <h2>Continue the work</h2>
        {reviewer && (
          <button
            className="secondary"
            disabled={busy || !claims.length}
            onClick={() => setAdding(!adding)}
          >
            <Plus size={15} />
            Create action
          </button>
        )}
      </div>
      <p className="advanced-help">
        Human-owned next steps linked to approved evidence. Action changes
        require a fresh acknowledgement.
      </p>
      {adding && (
        <form
          className="advanced-form"
          onSubmit={(e) => {
            e.preventDefault();
            act(async () => {
              await api("/actions", "POST", {
                claim_id: claimId,
                title,
                owner,
                phase,
                due: due || null,
              });
              setAdding(false);
              setTitle("");
            }, "Continuation action created.");
          }}
        >
          <label>
            Supporting approved claim
            <select
              required
              value={claimId}
              onChange={(e) => setClaimId(e.target.value)}
            >
              <option value="">Choose a receipt…</option>
              {claims
                .filter((c) => !c.restricted)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.text.slice(0, 120)}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Next action
            <input
              required
              minLength={3}
              maxLength={500}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Add an idempotency test for duplicate webhook events"
            />
          </label>
          <div className="form-columns">
            <label>
              Owner
              <input
                required
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
              />
            </label>
            <label>
              When
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value as Action["phase"])}
              >
                {["Day 1", "Week 1", "Day 30"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            <label>
              Due date
              <input
                type="date"
                value={due}
                onChange={(e) => setDue(e.target.value)}
              />
            </label>
          </div>
          <button className="primary" disabled={busy}>
            Save action
          </button>
        </form>
      )}
      <div className="plan-grid">
        {(["Day 1", "Week 1", "Day 30"] as const).map((phase) => (
          <section className="plan-column" key={phase}>
            <span className="eyebrow">{phase}</span>
            <h2>
              {
                actions.filter((a) => a.phase === phase && a.status === "done")
                  .length
              }
              /{actions.filter((a) => a.phase === phase).length} completed
            </h2>
            {actions
              .filter((a) => a.phase === phase)
              .map((a) => (
                <ActionRow
                  key={a.id + a.updated_at}
                  item={a}
                  api={api}
                  act={act}
                  busy={busy}
                  reviewer={reviewer}
                  name={name}
                  onReceipt={() => {
                    const claim = claims.find((c) => c.id === a.claim_id);
                    if (claim) onInspect(claim);
                  }}
                />
              ))}
            {!actions.some((a) => a.phase === phase) && (
              <p className="advanced-help">No actions scheduled here yet.</p>
            )}
          </section>
        ))}
      </div>
    </section>
  );
}
function ActionRow({
  item,
  api,
  act,
  busy,
  reviewer,
  name,
  onReceipt,
}: { item: Action; name: string; onReceipt: () => void } & Shared) {
  const [editing, setEditing] = useState(false),
    [value, setValue] = useState(item);
  const allowed = reviewer || item.owner.toLowerCase() === name.toLowerCase();
  const save = () =>
    act(async () => {
      await api("/actions/" + item.id, "PATCH", {
        title: value.title,
        owner: value.owner,
        phase: value.phase,
        due: value.due || null,
        status: value.status,
      });
      setEditing(false);
    }, "Action updated; previous receipts need review.");
  return (
    <article
      className={"action-item " + (item.status === "done" ? "action-done" : "")}
    >
      <span
        className={
          "badge " + (item.status === "blocked" ? "conflicting" : "verified")
        }
      >
        {item.status.replaceAll("_", " ")}
      </span>
      <h3>{item.title}</h3>
      <p>
        {item.owner} · {item.due || "No due date"} · version {item.version}
      </p>
      <div className="action-buttons">
        <button className="text-button" onClick={onReceipt}>
          Evidence <ArrowUpRight size={13} />
        </button>
        {allowed && (
          <button className="text-button" onClick={() => setEditing(!editing)}>
            Update action
          </button>
        )}
      </div>
      {editing && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <label>
            Action title
            <input
              required
              minLength={3}
              value={value.title}
              onChange={(e) => setValue({ ...value, title: e.target.value })}
            />
          </label>
          <label>
            Owner
            <input
              required
              disabled={!reviewer}
              value={value.owner}
              onChange={(e) => setValue({ ...value, owner: e.target.value })}
            />
          </label>
          <label>
            Timeframe
            <select
              value={value.phase}
              onChange={(e) =>
                setValue({ ...value, phase: e.target.value as Action["phase"] })
              }
            >
              {["Day 1", "Week 1", "Day 30"].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
          <label>
            Due date
            <input
              type="date"
              value={value.due || ""}
              onChange={(e) => setValue({ ...value, due: e.target.value })}
            />
          </label>
          <label>
            Status
            <select
              value={value.status}
              onChange={(e) =>
                setValue({
                  ...value,
                  status: e.target.value as Action["status"],
                })
              }
            >
              {["todo", "in_progress", "blocked", "done"].map((x) => (
                <option key={x} value={x}>
                  {x.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          <button className="primary" disabled={busy}>
            <CheckCheck size={15} />
            Save changes
          </button>
        </form>
      )}
    </article>
  );
}

export function QuestionQueue({
  claims, assignments, api, act, busy, reviewer, sudden, onInspect,
}: {
  claims: Claim[];
  assignments: Assignment[];
  sudden: boolean;
  onInspect: (claim: Claim) => void;
} & Shared) {
  const [members, setMembers] = useState<Member[]>([]);
  const [memberError, setMemberError] = useState("");
  useEffect(() => {
    if (!reviewer || busy) return;
    let cancelled = false;
    api("/members").then((rows: Member[]) => {
      if (!cancelled) {
        setMembers(rows.filter((member) => member.active));
        setMemberError("");
      }
    }).catch((error: Error) => {
      if (!cancelled) setMemberError(error.message);
    });
    return () => { cancelled = true; };
  }, [reviewer, busy, api]);
  const assigned = new Set(assignments.map((item) => item.claim_id));
  const unassigned = claims.filter((claim) => !assigned.has(claim.id));
  const rank = { high: 0, medium: 1, low: 2 };
  return (
    <section className="advanced-section">
      <div className="section-heading">
        <h2>Ask the leaver</h2>
        {reviewer && (
          <button className="primary" disabled={busy || !unassigned.length} onClick={() =>
            act(() => api("/questions/generate", "POST"), "Questions generated from unresolved context.")
          }>Generate questions</button>
        )}
      </div>
      {memberError && <p role="alert">{memberError}</p>}
      {reviewer && unassigned.length > 0 && <p className="muted">{unassigned.length} unresolved gaps are ready for questions.</p>}
      {!reviewer && unassigned.map((claim) => (
        <article className="question-row" key={claim.id}>
          <p>{claim.text}</p>
          <button className="secondary" onClick={() => onInspect(claim)}>Open gap and evidence</button>
        </article>
      ))}
      {[...assignments].sort((a, b) => rank[a.priority] - rank[b.priority]).map((item) => (
        <QuestionRow
          key={item.id + (item.assignee_id ?? item.assignee)}
          question={item}
          members={members}
          api={api}
          act={act}
          busy={busy}
          reviewer={reviewer}
          sudden={sudden}
        />
      ))}
    </section>
  );
}

function QuestionRow({ question, members, api, act, busy, reviewer, sudden }: {
  question: Assignment;
  members: Member[];
  sudden: boolean;
} & Shared) {
  const [answer, setAnswer] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const latest = question.answers.at(-1);
  const canRoute = reviewer && question.claim_status === "gap" && question.claim_review === "pending";
  return (
    <article className="question-row">
      <div>
        <span className="badge gap">{question.answered_at ? "Confirmed" : latest ? "Awaiting review" : "Open"}</span>
        <h3>{question.prompt}</h3>
        <p>
          {question.assignee_name ?? (sudden ? "Reviewer" : question.assignee)}
          {" · "}{question.priority} priority{question.due ? " · Due " + question.due : ""}
        </p>
        <EvidenceDisclosure load={() => api(`/questions/${question.id}/evidence`)} />
        {latest && (
          <div className="question-answer">
            <strong>Latest answer from {latest.by}</strong>
            <p>{latest.text}</p>
            {latest.follow_up && <p><strong>Suggested follow-up</strong> {latest.follow_up}</p>}
          </div>
        )}
        {question.can_confirm && (
          <button className="secondary" disabled={busy} onClick={() =>
            act(() => api(`/questions/${question.id}/confirm`, "POST"), "Answer confirmed. Approve the claim in Review before publishing.")
          }>Confirm answer for review</button>
        )}
      </div>
      {canRoute && (
        <form onSubmit={(event) => {
          event.preventDefault();
          const fields = new FormData(event.currentTarget);
          const target = String(fields.get("target"));
          act(() => api("/questions/assign", "POST", {
            claim_id: question.claim_id,
            priority: fields.get("priority"),
            due: fields.get("due") || null,
            assignee: target === "leaver" ? "leaver" : "reviewer",
            assignee_id: target.startsWith("member:") ? target.slice(7) : null,
          }), "Question routing saved.");
        }}>
          <div className="form-columns">
            <label>
              Assign to
              <select name="target" defaultValue={question.assignee_id ? "member:" + question.assignee_id : sudden ? "reviewer" : question.assignee}>
                <option value="reviewer">Reviewer</option>
                {!sudden && <option value="leaver">Departing member</option>}
                {members.filter((member) => !sudden || member.role !== "leaver").map((member) => (
                  <option key={member.id} value={"member:" + member.id}>{member.name} · {member.role}</option>
                ))}
              </select>
            </label>
            <label>
              Priority
              <select name="priority" defaultValue={question.priority}>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </label>
            <label>
              Due date
              <input name="due" type="date" defaultValue={question.due ?? ""} />
            </label>
          </div>
          <button className="secondary" disabled={busy}>Save assignment</button>
        </form>
      )}
      {question.can_answer && (
        <form onSubmit={(event) => {
          event.preventDefault();
          act(async () => {
            await api(`/questions/${question.id}/answer`, "POST", { text: answer, uncertain });
            setAnswer("");
            setUncertain(false);
          }, "Answer saved for reviewer confirmation.");
        }}>
          <label>
            {latest?.follow_up ? "Follow-up answer" : "Answer"}
            <textarea value={answer} onChange={(event) => setAnswer(event.target.value)} required maxLength={2000} />
          </label>
          {!latest && question.answer_hint && <p className="muted">{question.answer_hint}</p>}
          <label className="check-label">
            <input type="checkbox" checked={uncertain} onChange={(event) => setUncertain(event.target.checked)} />
            I still need to verify this answer
          </label>
          <button className="primary" disabled={busy}>Send answer for review</button>
        </form>
      )}
    </article>
  );
}

type Member = {
  id: string;
  username: string;
  name: string;
  role: string;
  active: boolean;
};
export function TeamPanel({
  api,
  act,
  busy,
}: {
  api: Api;
  act: Act;
  busy: boolean;
}) {
  const [members, setMembers] = useState<Member[]>([]),
    [username, setUsername] = useState(""),
    [name, setName] = useState(""),
    [role, setRole] = useState("successor"),
    [code, setCode] = useState("");
  useEffect(() => {
    let cancelled = false;
    api("/members")
      .then((data) => {
        if (!cancelled) setMembers(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [busy]);
  return (
    <section>
      <div className="callout">
        <UserPlus />
        <div>
          <strong>Named accounts, scoped to the project</strong>
          <p>
            Invite a new or existing username to this project. Invitations expire after 24 hours.
          </p>
        </div>
      </div>
      <form
        className="advanced-form"
        onSubmit={(e) => {
          e.preventDefault();
          act(async () => {
            const result = await api("/invites", "POST", {
              username,
              name,
              role,
            });
            setCode(result.code);
          }, "One-time invitation created. Share it only with the intended recipient.");
        }}
      >
        <div className="form-columns">
          <label>
            Username
            <input
              required
              minLength={3}
              pattern="[A-Za-z0-9_.@+\-]+"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="meera.backend"
            />
          </label>
          <label>
            Display name
            <input
              required
              minLength={2}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            Project role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {["successor", "coordinator", "leaver", "reviewer"].map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
        </div>
        <button className="primary" disabled={busy}>
          <UserPlus size={15} />
          Create invitation
        </button>
        {code && (
          <div className="invite-code" role="status">
            <strong>Invitation for {username}</strong>
            <p>
              Choose “Join with invitation” on the sign-in screen and enter this
              code:
            </p>
            <code>{code}</code>
            <p>Valid for 24 hours; usable once.</p>
          </div>
        )}
      </form>
      <div className="section-heading">
        <h2>Project members</h2>
        <span className="muted">
          Revocation takes effect on the next request
        </span>
      </div>
      <div className="member-list">
        {members.map((m) => (
          <div key={m.id} className="member-row">
            <span className="avatar">{m.name[0]}</span>
            <span>
              <strong>{m.name}</strong>
              <small>
                {m.username} · {m.role} · {m.active ? "active" : "revoked"}
              </small>
            </span>
            <button
              className="secondary"
              disabled={busy}
              onClick={() =>
                act(
                  () => api("/members/" + m.id, "PATCH", { active: !m.active }),
                  "Access to this project updated.",
                )
              }
            >
              {m.active ? "Revoke access" : "Restore access"}
            </button>
          </div>
        ))}
        {!members.length && (
          <p className="advanced-help" style={{ padding: 20 }}>
            No named members yet.
          </p>
        )}
      </div>
    </section>
  );
}

export function JoinWorkspace({
  api,
  onBack,
  onJoined,
}: {
  api: Api;
  onBack: () => void;
  onJoined: (username: string) => void;
}) {
  const [code, setCode] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <main className="join-form">
      <span className="eyebrow">PASS THE CONTEXT FORWARD</span>
      <h1>Join your project.</h1>
      <p>
        Use the one-time code provided by your reviewer. Your project role is
        set by the invitation. Enter your existing password if you already have an account.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const result = await api("/register", "POST", { code, password });
            setPassword("");
            onJoined(result.username);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Invitation code
          <input
            required
            minLength={20}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            autoComplete="off"
          />
        </label>
        <label>
          Account password (at least 12 characters)
          <input
            required
            type="password"
            minLength={12}
            maxLength={200}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
        </label>
        {error && (
          <div role="alert" className="error">
            {error}
          </div>
        )}
        <button className="primary full" disabled={busy}>
          {busy ? "Joining…" : "Join project"}
        </button>
      </form>
      <div className="login-extra">
        <button className="text-button" onClick={onBack}>
          Back to sign in
        </button>
      </div>
    </main>
  );
}
