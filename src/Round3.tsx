import { useId, useState } from "react";

export type Project = { id: number; name: string; role: string };

export function Projects({ projects, current, canCreate, busy, onSwitch, onCreate }: {
  projects: Project[];
  current: number;
  canCreate: boolean;
  busy: boolean;
  onSwitch: (id: number) => void;
  onCreate: (name: string) => void;
}) {
  const [name, setName] = useState("");
  const projectLabel = useId();
  return (
    <div className="project-controls">
      <label>
        <span id={projectLabel}>Project</span>
        <select aria-labelledby={projectLabel} value={current} disabled={busy} onChange={(event) => onSwitch(Number(event.target.value))}>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>{project.name} · {project.role}</option>
          ))}
        </select>
      </label>
      {canCreate && (
        <details>
          <summary>New project</summary>
          <form onSubmit={(event) => {
            event.preventDefault();
            if (name.trim().length >= 2) onCreate(name.trim());
          }}>
            <label>
              Project name
              <input value={name} onChange={(event) => setName(event.target.value)} required minLength={2} maxLength={100} />
            </label>
            <button className="secondary" disabled={busy}>Create project</button>
          </form>
        </details>
      )}
    </div>
  );
}

type Quote = { source: string; source_id: string; locator: string; quote: string; found: boolean };

export function EvidenceDisclosure({ load }: { load: () => Promise<Quote[]> }) {
  const [quotes, setQuotes] = useState<Quote[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <div className="round3-evidence">
      <button type="button" className="secondary" aria-expanded={quotes !== null} disabled={busy} onClick={async () => {
        if (quotes !== null) {
          setQuotes(null);
          return;
        }
        setBusy(true);
        setError("");
        try {
          setQuotes(await load());
        } catch (error) {
          setError((error as Error).message);
        } finally {
          setBusy(false);
        }
      }}>
        {busy ? "Loading evidence…" : quotes ? "Hide evidence" : "View evidence"}
      </button>
      {error && <p role="alert">{error}</p>}
      {quotes?.map((item, index) => (
        <blockquote key={item.source_id + item.locator + index}>
          <p>{item.quote}</p>
          <footer>{item.source} · {item.locator}{item.found ? "" : " · Quote needs checking"}</footer>
        </blockquote>
      ))}
    </div>
  );
}

type Change = { id: string; text: string; owner: string };
export type CatchUpData = {
  latest_version: number | null;
  baseline: { version: number; at: string; section: string } | null;
  responsibilities: (Change & { previous_owner: string })[];
  risks: Change[];
  actions: { id: string; claim_id: string; version: number; title: string; owner: string; due: string | null; status: string; overdue: boolean }[];
};

export function CatchUp({ data, evidence }: {
  data: CatchUpData;
  evidence: (id: string, version: number) => Promise<Quote[]>;
}) {
  const version = data.latest_version;
  if (version === null) return null;
  return (
    <section className="advanced-section catch-up">
      <h2>Your catch-up</h2>
      <p className="advanced-help">
        {data.baseline
          ? `Compared with version ${data.baseline.version}, which you acknowledged for ${data.baseline.section}. Current version ${version}.`
          : `This is your first review of version ${version}. Acknowledge a section below to set your comparison point.`}
      </p>
      <h3>Changed responsibilities</h3>
      {!data.responsibilities.length && <p className="muted">No visible ownership changes.</p>}
      {data.responsibilities.map((item) => (
        <article key={item.id}>
          <p>{item.text}</p>
          <p className="muted">{item.previous_owner} → {item.owner} · Version {version}</p>
          <EvidenceDisclosure load={() => evidence(item.id, version)} />
        </article>
      ))}
      <h3>{data.baseline ? "Newly approved risks" : "Risks to review"}</h3>
      {!data.risks.length && <p className="muted">No new risks in your view.</p>}
      {data.risks.map((item) => (
        <article key={item.id}>
          <p>{item.text}</p>
          <p className="muted">{item.owner} · Version {version}</p>
          <EvidenceDisclosure load={() => evidence(item.id, version)} />
        </article>
      ))}
      <h3>Overdue or blocked actions</h3>
      {!data.actions.length && <p className="muted">No overdue or blocked actions in your view.</p>}
      {data.actions.map((item) => (
        <article key={item.id}>
          <p>{item.title}</p>
          <p className="muted">
            {item.owner} · {item.status === "blocked" ? "Blocked" : "Overdue"}
            {item.status === "blocked" && item.overdue ? " and overdue" : ""}
            {item.due ? ` · Due ${item.due}` : ""} · Version {item.version}
          </p>
          <EvidenceDisclosure load={() => evidence(item.claim_id, item.version)} />
        </article>
      ))}
    </section>
  );
}
