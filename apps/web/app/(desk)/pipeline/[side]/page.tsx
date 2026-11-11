"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import Link from "next/link";
import { use, useEffect, useState } from "react";

type Company = { id: string; legal_name: string; country: string; supplier_stage: string | null; buyer_stage: string | null; verification_status: string };

export default function PipelinePage({ params }: { params: Promise<{ side: string }> }) {
  const { side } = use(params);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!side) return;
    api<{ companies: Company[] }>(`/pipeline/${side}`).then((data) => setCompanies(data.companies)).catch((reason: Error) => setError(reason.message));
  }, [side]);

  const supplier = side === "suppliers";
  return (
    <>
      <PageTitle kicker="Pipeline" title={supplier ? "Supplier pipeline" : "Buyer pipeline"} text="Stages move one step at a time. Illegal jumps are rejected by the API." />
      <ErrorNote message={error} />
      <Panel>
        {companies.length === 0 ? <p className="text-sm text-muted">No companies on this side yet.</p> : (
          <table>
            <thead><tr><th>Company</th><th>Stage</th><th>Verification</th></tr></thead>
            <tbody>
              {companies.map((company) => (
                <tr key={company.id}>
                  <td><Link className="underline" href={`/companies/${company.id}`}>{company.legal_name}</Link><div className="text-xs text-muted">{company.country}</div></td>
                  <td>{supplier ? company.supplier_stage : company.buyer_stage}</td>
                  <td>{company.verification_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </>
  );
}
