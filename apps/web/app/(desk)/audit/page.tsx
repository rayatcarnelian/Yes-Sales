"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

type AuditCase = {
  code: string;
  title: string;
  status: string;
  executed_at: string;
  failure_reason: string | null;
  evidence: Record<string, unknown>;
};

type Report = {
  source?: string;
  status?: string;
  database_name?: string;
  connected_database?: string;
  isolated_from_connected_database?: boolean;
  started_at?: string;
  finished_at?: string;
  cases?: AuditCase[];
  summary?: {
    tested_capabilities: string[];
    untested_capabilities: string[];
    passed_tests: string[];
    failed_tests: string[];
    mocked_tests: string[];
    skipped_tests: string[];
    research_accuracy: { ratio: string; claims_checked: number; incorrectly_accepted: number; note: string };
    qualified_sales_opportunities: number;
    rfqs: number;
    human_intervention: { seconds: string | null; reason: string | null; decisions_measured: number };
    per_agent_cost_usd: Record<string, string>;
    commission_status: Array<{ collection_status: string; count: number }>;
    pending_approvals: number;
    alex_outcomes: { rows: number; comparable_pairs: number; note: string };
  } | null;
};

export default function AuditPage() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Report>("/audit/commercial").then(setReport).catch((reason: Error) => setError(reason.message));
  }, []);

  const summary = report?.summary;

  return (
    <>
      <PageTitle kicker="Audit" title="Commercial test record" text="Figures come from the latest staging run. A mocked or skipped case is not shown as passed." />
      <ErrorNote message={error} />
      {!summary ? <Panel><p className="text-sm text-muted">{report?.status === "not_run" ? "No audit run is stored yet." : "Loading the audit record."}</p></Panel> : (
        <>
          <Panel>
            <p className="text-sm">Run status: {report?.status}. Source: {report?.source}. Staging database: {report?.database_name}. Connected database: {report?.connected_database}.</p>
            {report?.isolated_from_connected_database ? <p className="mt-2 text-sm text-muted">This record is from the isolated staging run. It is not a count from the operating database.</p> : null}
            <p className="mt-2 text-sm text-muted">{report?.started_at} to {report?.finished_at}</p>
          </Panel>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Panel><p className="text-xs uppercase text-muted">Passed</p><p className="mt-2 font-serif text-3xl">{summary.passed_tests.length}</p></Panel>
            <Panel><p className="text-xs uppercase text-muted">Failed</p><p className="mt-2 font-serif text-3xl">{summary.failed_tests.length}</p></Panel>
            <Panel><p className="text-xs uppercase text-muted">Mocked</p><p className="mt-2 font-serif text-3xl">{summary.mocked_tests.length}</p></Panel>
            <Panel><p className="text-xs uppercase text-muted">Skipped</p><p className="mt-2 font-serif text-3xl">{summary.skipped_tests.length}</p></Panel>
            <Panel><p className="text-xs uppercase text-muted">Research controls</p><p className="mt-2 font-serif text-3xl">{summary.research_accuracy.ratio}</p><p className="mt-1 text-xs text-muted">{summary.research_accuracy.note}</p></Panel>
            <Panel><p className="text-xs uppercase text-muted">Qualified opportunities</p><p className="mt-2 font-serif text-3xl">{summary.qualified_sales_opportunities}</p></Panel>
            <Panel><p className="text-xs uppercase text-muted">RFQs</p><p className="mt-2 font-serif text-3xl">{summary.rfqs}</p></Panel>
            <Panel><p className="text-xs uppercase text-muted">Pending approvals</p><p className="mt-2 font-serif text-3xl">{summary.pending_approvals}</p></Panel>
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Panel>
              <h2 className="font-medium">Tested capabilities</h2>
              <ul className="mt-3 grid gap-1 text-sm">{summary.tested_capabilities.map((item) => <li key={item}>{item}</li>)}</ul>
            </Panel>
            <Panel>
              <h2 className="font-medium">Untested capabilities</h2>
              <ul className="mt-3 grid gap-1 text-sm">{summary.untested_capabilities.map((item) => <li key={item}>{item}</li>)}</ul>
            </Panel>
          </div>
          <Panel className="mt-4">
            <p className="text-sm">Human intervention time: {summary.human_intervention.seconds ?? "not measured"}. {summary.human_intervention.reason}</p>
            <p className="mt-2 text-sm">Commission status: {summary.commission_status.map((item) => `${item.collection_status} ${item.count}`).join(", ")}</p>
            <p className="mt-2 text-sm">Per-agent cost USD: {Object.entries(summary.per_agent_cost_usd).map(([name, value]) => `${name} ${value}`).join(", ") || "No provider cost recorded."}</p>
            <p className="mt-2 text-sm">Alex outcomes stored: {summary.alex_outcomes.rows}. Comparable human-versus-AI pairs: {summary.alex_outcomes.comparable_pairs}. {summary.alex_outcomes.note}</p>
          </Panel>
          <div className="mt-4 grid gap-3">
            {report?.cases?.map((item) => (
              <Panel key={item.code}>
                <div className="flex items-baseline justify-between gap-3">
                  <h2 className="font-medium">{item.title}</h2>
                  <span className="text-xs uppercase text-muted">{item.status}</span>
                </div>
                <p className="mt-1 text-xs text-muted">{item.executed_at}</p>
                {item.failure_reason ? <p className="mt-2 text-sm">{item.failure_reason}</p> : null}
              </Panel>
            ))}
          </div>
        </>
      )}
    </>
  );
}