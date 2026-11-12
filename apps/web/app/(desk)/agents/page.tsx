"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import { FormEvent, useEffect, useState } from "react";

type Task = { id: string; task_type: string; status: string; attempt: number; last_error: string | null };
type Settings = { outbound_paused: boolean; jobs_paused: boolean; budget_ceiling_usd: string; budget_spent_usd: string };
type Integrations = Record<string, string | boolean>;
type Seat = { seat: string; agent: string; job?: string; status?: string; message?: string };
type Play = { research_agent: string; next_step: string; sent: boolean; verification_trusted: boolean; outreach_authorized: boolean; price_bound: boolean; payment_executed: boolean; companies_created: boolean; seats: Seat[] };

export default function AgentsPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [integrations, setIntegrations] = useState<Integrations>({});
  const [roster, setRoster] = useState<Seat[]>([]);
  const [play, setPlay] = useState<Play | null>(null);
  const [brief, setBrief] = useState("");
  const [country, setCountry] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function load() {
    Promise.all([
      api<{ tasks: Task[] }>("/tasks"),
      api<Settings>("/settings"),
      api<Integrations>("/integrations"),
      api<{ seats: Seat[] }>("/sales-team"),
    ]).then(([taskData, settingData, integrationData, team]) => {
      setTasks(taskData.tasks);
      setSettings(settingData);
      setIntegrations(integrationData);
      setRoster(team.seats);
    }).catch((reason: Error) => setError(reason.message));
  }

  useEffect(() => { load(); }, []);

  async function pause(paused: boolean) {
    try {
      await api("/settings/outbound-pause", { method: "POST", body: JSON.stringify({ paused }) });
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Pause was not changed");
    }
  }

  async function pauseJobs(paused: boolean) {
    try {
      await api("/settings/jobs-pause", { method: "POST", body: JSON.stringify({ paused }) });
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Job pause was not changed");
    }
  }

  async function retry(id: string) {
    try {
      await api(`/tasks/${id}/retry`, { method: "POST" });
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Retry failed");
    }
  }

  async function runFloor(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<Play>("/sales-team/run", {
        method: "POST",
        body: JSON.stringify({
          brief,
          country: country.trim() || null,
          company_id: companyId.trim() || null,
          source_url: sourceUrl,
          excerpt,
        }),
      });
      setPlay(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The floor did not run");
    } finally {
      setBusy(false);
    }
  }

  const failed = tasks.filter((task) => task.status === "failed" || task.status === "dead");

  return (
    <>
      <PageTitle kicker="Sales team" title="The floor" text="Atlas manages. One researcher files a source you already opened. Guard checks the text. Alex classifies. Ledger holds the price. Nothing is sent." />
      <ErrorNote message={error} />
      <Panel className="mb-4">
        <h2 className="font-medium">Run one account</h2>
        <p className="mt-1 text-sm text-muted">Paste a brief and, when the company is already on the desk, the page that names it. The floor does not create a company and does not send.</p>
        <form className="mt-3 grid gap-3" onSubmit={runFloor}>
          <textarea className="min-h-20 border border-line bg-transparent px-3 py-2 text-sm" placeholder="Brief. What should the floor look at?" value={brief} onChange={(event) => setBrief(event.target.value)} required />
          <div className="grid gap-3 md:grid-cols-3">
            <input className="border border-line bg-transparent px-3 py-2 text-sm" placeholder="Country, two letters" value={country} onChange={(event) => setCountry(event.target.value)} />
            <input className="border border-line bg-transparent px-3 py-2 text-sm" placeholder="Company id, if it is already open" value={companyId} onChange={(event) => setCompanyId(event.target.value)} />
            <input className="border border-line bg-transparent px-3 py-2 text-sm" placeholder="Page address of the source" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} />
          </div>
          <textarea className="min-h-24 border border-line bg-transparent px-3 py-2 text-sm" placeholder={"Source text, including a Company: line"} value={excerpt} onChange={(event) => setExcerpt(event.target.value)} />
          <button className="w-fit bg-accent px-4 py-2 text-sm text-[var(--accent-ink)] disabled:opacity-60" type="submit" disabled={busy || !brief.trim()}>{busy ? "Running" : "Run the floor"}</button>
        </form>
        {play && (
          <div className="mt-4 grid gap-2 text-sm">
            <p>Next step: {play.next_step}</p>
            <p className="text-muted">Researcher {play.research_agent}. Sent {String(play.sent)}. Verified by the floor {String(play.verification_trusted)}. Price bound {String(play.price_bound)}. Payment {String(play.payment_executed)}. Company created {String(play.companies_created)}.</p>
            {play.seats.map((seat) => (
              <p key={seat.seat}>{seat.agent} · {seat.status}: {seat.message}</p>
            ))}
          </div>
        )}
      </Panel>
      <Panel className="mb-4">
        <h2 className="font-medium">Seats</h2>
        <div className="mt-3 grid gap-2 text-sm">
          {roster.map((seat) => (
            <p key={seat.agent}><span className="font-medium">{seat.agent}</span> · {seat.job}</p>
          ))}
        </div>
      </Panel>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <h2 className="font-medium">App controls</h2>
          <p className="mt-2 text-sm">App outbound: {settings ? (settings.outbound_paused ? "paused" : "running") : "…"}</p>
          <p className="text-sm text-muted">Blocks email and callbacks sent by this app.</p>
          <div className="mt-3 flex gap-2">
            <button className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" type="button" onClick={() => pause(true)}>Pause outbound</button>
            <button className="border border-line px-4 py-2 text-sm" type="button" onClick={() => pause(false)}>Resume outbound</button>
          </div>
          <p className="mt-4 text-sm">App jobs: {settings ? (settings.jobs_paused ? "paused" : "running") : "…"}</p>
          <p className="text-sm text-muted">Stops this app from running queued tasks. It does not pause Grok or change Grok credits.</p>
          <div className="mt-3 flex gap-2">
            <button className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" type="button" onClick={() => pauseJobs(true)}>Pause app jobs</button>
            <button className="border border-line px-4 py-2 text-sm" type="button" onClick={() => pauseJobs(false)}>Resume app jobs</button>
          </div>
          <p className="mt-4 text-sm">Grok model: {integrations.grok_connected ? "key saved, not verified" : "not configured"}</p>
          <p className="text-sm text-muted">
            Bot post door: {String(integrations.grok_bot_ingest || "not_configured")}. Credit control: {String(integrations.grok_credit_control || "none")}. A saved key is not a completed model call, and this desk cannot pause Grok or spend its credits.
          </p>
          <p className="mt-3 text-sm text-muted">Budget {settings?.budget_spent_usd || "…"} / {settings?.budget_ceiling_usd || "…"} USD</p>
        </Panel>
        <Panel>
          <h2 className="font-medium">Providers</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(integrations).map(([name, value]) => <span key={name} className="rounded-full border border-line px-3 py-1 text-xs">{name}: {String(value)}</span>)}
          </div>
        </Panel>
      </div>
      <Panel className="mt-4">
        <h2 className="font-medium">Failed tasks</h2>
        {failed.length === 0 ? <p className="mt-2 text-sm text-muted">No failed or dead tasks.</p> : failed.map((task) => (
          <div key={task.id} className="mt-3 flex items-center justify-between gap-3 text-sm">
            <div>
              <p>{task.task_type} · {task.status} · attempt {task.attempt}</p>
              <p className="text-muted">{task.last_error}</p>
            </div>
            <button className="border border-line px-3 py-1" type="button" onClick={() => retry(task.id)}>Restart</button>
          </div>
        ))}
      </Panel>
    </>
  );
}
