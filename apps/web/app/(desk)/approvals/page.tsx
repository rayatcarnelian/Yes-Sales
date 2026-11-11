"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

type Approval = {
  id: string;
  action_type: string;
  status: string;
  notes: string | null;
  decision_note: string | null;
  subject_type: string;
  outcome: { result?: string; executed?: boolean; provider_mode?: string; live_email?: boolean; reason?: string } | null;
};

export default function ApprovalsPage() {
  const [rows, setRows] = useState<Approval[]>([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("Reviewed by founder");

  function load() {
    api<{ approvals: Approval[] }>("/approvals").then((data) => setRows(data.approvals)).catch((reason: Error) => setError(reason.message));
  }

  useEffect(() => { load(); }, []);

  async function act(id: string, path: string, body?: object) {
    setError("");
    try {
      await api(`/approvals/${id}/${path}`, { method: "POST", body: body ? JSON.stringify(body) : undefined });
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Action failed");
    }
  }

  return (
    <>
      <PageTitle kicker="Founder" title="Approval center" text="Pending decisions stay listed until you approve or reject them. An executed action shows the stored outcome, including a mock send or a payment that was not executed." />
      <ErrorNote message={error} />
      <Panel className="mb-4">
        <label className="text-sm">Decision note<textarea className="mt-1" rows={2} value={note} onChange={(event) => setNote(event.target.value)} /></label>
      </Panel>
      <div className="grid gap-3">
        {rows.length === 0 ? <Panel><p className="text-sm text-muted">No approval requests.</p></Panel> : rows.map((row) => (
          <Panel key={row.id}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-medium">{row.action_type}</h2>
                <p className="text-sm text-muted">{row.subject_type} · {row.status}</p>
                <p className="mt-1 text-sm">{row.notes || row.decision_note || "No note"}</p>
                {row.outcome ? <p className="mt-1 text-sm">Outcome {row.outcome.result}{row.outcome.provider_mode ? ` · ${row.outcome.provider_mode}` : ""}{row.outcome.executed === false ? " · not executed" : ""}</p> : null}
              </div>
              {row.status === "pending" ? (
                <div className="flex gap-2">
                  <button className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" type="button" onClick={() => act(row.id, "decide", { decision: "approved", note })}>Approve</button>
                  <button className="border border-line px-4 py-2 text-sm" type="button" onClick={() => act(row.id, "decide", { decision: "rejected", note })}>Reject</button>
                </div>
              ) : null}
              {row.status === "approved" && !row.outcome ? <button className="border border-line px-4 py-2 text-sm" type="button" onClick={() => act(row.id, "execute")}>Execute recorded action</button> : null}
            </div>
          </Panel>
        ))}
      </div>
    </>
  );
}
