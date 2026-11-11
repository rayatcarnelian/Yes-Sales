"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import Link from "next/link";
import { useEffect, useState } from "react";

type Kpis = Record<string, string | number | boolean | Record<string, string | boolean>>;

const CARDS: Array<[string, string]> = [
  ["verified_suppliers", "Verified suppliers"],
  ["qualified_buyers", "Qualified buyers"],
  ["active_conversations", "Active conversations"],
  ["rfqs", "RFQs"],
  ["supplier_quotations", "Supplier quotations"],
  ["matched_opportunities", "Matched opportunities"],
  ["deals_requiring_approval", "Deals requiring approval"],
  ["pipeline_value", "Pipeline value"],
  ["contracted_commissions", "Contracted commissions"],
  ["collected_commissions", "Collected commissions"],
  ["agent_errors", "Agent errors"],
  ["api_costs", "API costs"],
];

export default function CommandPage() {
  const [data, setData] = useState<Kpis | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Kpis>("/dashboard/kpis").then(setData).catch((reason: Error) => setError(reason.message));
  }, []);

  const integrations = (data?.integrations || {}) as Record<string, string | boolean>;

  return (
    <>
      <PageTitle kicker="Start" title="Two desks" text="Pick the work you are doing. The detailing shop and the export desk do not share a workflow. Email, WhatsApp, and the Grok model stay off until you connect them." />
      <ErrorNote message={error} />
      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <Panel>
          <p className="text-xs uppercase tracking-[0.14em] text-[var(--gold)]">Detailing shop</p>
          <p className="mt-2 font-medium">Take a car and a package</p>
          <p className="mt-1 text-sm text-muted">Approve a price, then save the request. The draft can repeat only that price. Nothing is sent.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" href="/job-cards">Job cards</Link>
            <Link className="border border-line px-4 py-2 text-sm" href="/approvals">Approvals</Link>
          </div>
        </Panel>
        <Panel>
          <p className="text-xs uppercase tracking-[0.14em] text-[var(--gold)]">Export desk</p>
          <p className="mt-2 font-medium">Suppliers, buyers, and bot files</p>
          <p className="mt-1 text-sm text-muted">Paste a Grok bot’s JSON on Grok files. The company stays unverified. A bot file is not a shop price.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" href="/agents">Run the sales team</Link>
            <Link className="border border-line px-4 py-2 text-sm" href="/research">Add a Grok file</Link>
            <Link className="border border-line px-4 py-2 text-sm" href="/companies">Companies</Link>
          </div>
        </Panel>
      </div>
      <p className="mb-3 text-sm text-muted">Export counts, read from the database.</p>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {CARDS.map(([key, label]) => (
          <Panel key={key}>
            <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
            <p className="mt-2 font-serif text-3xl">{data ? String(data[key] ?? "—") : "…"}</p>
          </Panel>
        ))}
      </div>
      <Panel className="mt-4">
        <p className="text-sm font-medium">Integration mode</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(integrations).map(([name, value]) => (
            <span key={name} className="rounded-full border border-line px-3 py-1 text-xs">
              {name}: {String(value)}
            </span>
          ))}
        </div>
        <div className="mt-3 grid gap-2 text-sm">
          <p>App outbound is {data ? (data.outbound_paused ? "paused" : "running") : "…"}. The outbound switch blocks email and callbacks from this app.</p>
          <p>App jobs is {data ? (data.jobs_paused ? "paused" : "running") : "…"}. The jobs switch stops this app from running queued tasks.</p>
          <p>
            Grok model: {integrations.grok_connected ? "connected" : "not connected"}.{" "}
            {integrations.grok_connected
              ? "Pausing app jobs does not stop Grok or control Grok credits."
              : "Add XAI_API_KEY in .env and restart the API to connect the model. A bot file can still be pasted on Grok files."}
          </p>
        </div>
      </Panel>
    </>
  );
}
