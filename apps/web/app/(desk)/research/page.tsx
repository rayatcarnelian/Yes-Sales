"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import Link from "next/link";
import { ChangeEvent, FormEvent, useEffect, useState } from "react";

type Task = { id: string; task_type: string; status: string; result: { note?: string; provider_mode?: string; companies?: unknown[] } | null; last_error: string | null };
type ImportRow = {
  id?: string;
  task_id?: string;
  company_identity?: string;
  company_id?: string | null;
  import_status: string;
  claimed_verification_status?: string | null;
  stored_verification_status?: string | null;
  rejection_reason?: string | null;
  idempotent_replay?: boolean;
  evidence_status?: string;
  claim_downgraded?: boolean;
  stored_as_research_source?: boolean;
};

export default function ResearchPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [imports, setImports] = useState<ImportRow[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ agent: "bengal", query: "", country: "BD" });
  const [paste, setPaste] = useState("");
  const [notice, setNotice] = useState("");

  function load() {
    api<{ tasks: Task[] }>("/tasks?status=").then((data) => setTasks(data.tasks.filter((task) => task.task_type === "research.search"))).catch((reason: Error) => setError(reason.message));
    api<{ imports: ImportRow[] }>("/research/bot-imports").then((data) => setImports(data.imports)).catch((reason: Error) => setError(reason.message));
  }

  useEffect(() => { load(); }, []);

  async function onImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = file.name.toLowerCase().endsWith(".csv") ? { csv: text } : JSON.parse(text);
      const body = Array.isArray(parsed) ? { records: parsed } : parsed;
      const result = await api<{ results: ImportRow[] }>("/research/bot-imports", { method: "POST", body: JSON.stringify(body) });
      setNotice(`Saved ${result.results.length} rows. A verified label stays a claim. Nothing was sent.`);
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Bot import failed");
    }
  }

  async function onPaste(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const parsed = JSON.parse(paste);
      const body = Array.isArray(parsed) ? { records: parsed } : parsed;
      const result = await api<{ results: ImportRow[] }>("/research/bot-imports", { method: "POST", body: JSON.stringify(body) });
      setPaste("");
      setNotice(`Saved ${result.results.length} rows. A verified label stays a claim. Nothing was sent.`);
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Paste the bot JSON as a records list.");
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/research/jobs", { method: "POST", body: JSON.stringify({ ...form, idempotency_key: `ui-${Date.now()}` }) });
      await api("/tasks/process", { method: "POST" });
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Research job failed");
    }
  }

  return (
    <>
      <PageTitle kicker="Orion, Bengal, Meridian, Hunter" title="Research jobs" text="Bring a Grok bot's finished JSON or CSV onto this desk. The company is stored unverified. The bot does not get the database, and it cannot send a message or approve a price." />
      <ErrorNote message={error} />
      {notice ? <p className="mb-4 text-sm text-[var(--ok)]">{notice}</p> : null}
      <Panel>
        <h2 className="font-medium">1. Paste the bot's JSON</h2>
        <p className="mt-1 text-sm text-muted">Use the records list the bot wrote. A VERIFIED label does not verify the company.</p>
        <form className="mt-3" onSubmit={onPaste}>
          <textarea rows={6} value={paste} onChange={(event) => setPaste(event.target.value)} placeholder='{"records":[...]}' />
          <button className="mt-3 bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" type="submit">Save bot output</button>
        </form>
        <h2 className="mt-6 font-medium">2. Or choose a file</h2>
        <input className="mt-3" type="file" accept=".json,.csv,application/json,text/csv" onChange={onImport} />
      </Panel>
      <div className="mt-4 grid gap-3">
        {imports.length === 0 ? <Panel><p className="text-sm text-muted">No bot imports yet.</p></Panel> : imports.map((row) => (
          <Panel key={row.id || row.task_id}>
            <p className="text-sm font-medium">{row.import_status} · {row.company_identity || row.task_id}</p>
            <p className="mt-1 text-sm text-muted">Task {row.task_id} · claimed {row.claimed_verification_status || "—"} · stored {row.stored_verification_status || "not stored"} · evidence {row.evidence_status || "held"}{row.claim_downgraded ? " · claim downgraded" : ""}{row.stored_as_research_source ? "" : " · not a source"}{row.idempotent_replay ? " · replay" : ""}</p>
            {row.rejection_reason ? <p className="mt-1 text-sm">{row.rejection_reason}</p> : null}
            {row.company_id ? <Link className="mt-2 inline-block text-sm underline" href={`/companies/${row.company_id}`}>Open in CRM</Link> : null}
          </Panel>
        ))}
      </div>
      <Panel>
        <form onSubmit={onSubmit} className="grid gap-3 md:grid-cols-4">
          <select value={form.agent} onChange={(event) => setForm({ ...form, agent: event.target.value })}>
            <option value="bengal">Bengal · Bangladesh</option>
            <option value="meridian">Meridian · Malaysia</option>
            <option value="hunter">Hunter · buyers</option>
            <option value="orion">Orion · market</option>
          </select>
          <input placeholder="Query" value={form.query} onChange={(event) => setForm({ ...form, query: event.target.value })} required />
          <input placeholder="Country" value={form.country} maxLength={2} onChange={(event) => setForm({ ...form, country: event.target.value.toUpperCase() })} />
          <button className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" type="submit">Queue job</button>
        </form>
      </Panel>
      <div className="mt-4 grid gap-3">
        {tasks.length === 0 ? <Panel><p className="text-sm text-muted">No research jobs yet.</p></Panel> : tasks.map((task) => (
          <Panel key={task.id}>
            <p className="text-sm font-medium">{task.status}</p>
            <p className="mt-1 text-sm text-muted">{task.result?.note || task.last_error || "Waiting"}</p>
            <p className="mt-1 text-xs">Mode {task.result?.provider_mode || "—"} · companies {task.result?.companies?.length ?? 0}</p>
          </Panel>
        ))}
      </div>
    </>
  );
}
