"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import { FormEvent, useEffect, useState } from "react";

type Deal = { id: string; title: string; stage: string; status: string; pipeline_value: string; currency: string; buyer_name: string | null; supplier_name: string | null; rfqs: Array<{ id: string; status: string }> };
type Company = { id: string; legal_name: string; role: string };

export default function DealsPage() {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ buyer_id: "", supplier_id: "", category: "", title: "" });

  function load() {
    api<{ opportunities: Deal[] }>("/opportunities").then((data) => setDeals(data.opportunities)).catch((reason: Error) => setError(reason.message));
    api<{ companies: Company[] }>("/companies").then((data) => setCompanies(data.companies)).catch((reason: Error) => setError(reason.message));
  }

  useEffect(() => { load(); }, []);

  async function createDeal(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const requirement = await api<{ id: string }>("/buyer-requirements", { method: "POST", body: JSON.stringify({ company_id: form.buyer_id, product_category: form.category }) });
      const opportunity = await api<{ id: string }>("/opportunities", {
        method: "POST",
        body: JSON.stringify({ buyer_company_id: form.buyer_id, supplier_company_id: form.supplier_id || null, buyer_requirement_id: requirement.id, title: form.title, pipeline_value: "0" }),
      });
      await api("/rfqs", { method: "POST", body: JSON.stringify({ buyer_requirement_id: requirement.id, opportunity_id: opportunity.id, notes: form.title }) });
      setForm({ buyer_id: "", supplier_id: "", category: "", title: "" });
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Deal was not created");
    }
  }

  const buyers = companies.filter((company) => company.role === "buyer" || company.role === "both");
  const suppliers = companies.filter((company) => company.role === "supplier" || company.role === "both");

  return (
    <>
      <PageTitle kicker="Ledger" title="Deals" text="An opportunity is stored with a buyer requirement and an RFQ. Pipeline value is the amount stored on the opportunity. Landed cost is never calculated." />
      <ErrorNote message={error} />
      <Panel className="mb-4">
        <form onSubmit={createDeal} className="grid gap-3 md:grid-cols-5">
          <select value={form.buyer_id} onChange={(event) => setForm({ ...form, buyer_id: event.target.value })} required>
            <option value="">Buyer</option>
            {buyers.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}
          </select>
          <select value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: event.target.value })}>
            <option value="">Supplier</option>
            {suppliers.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}
          </select>
          <input placeholder="Category" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} required />
          <input placeholder="Deal title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required />
          <button className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" type="submit">Create opportunity</button>
        </form>
      </Panel>
      <Panel>
        {deals.length === 0 ? <p className="text-sm text-muted">No opportunities yet.</p> : (
          <table>
            <thead><tr><th>Deal</th><th>Parties</th><th>Stage</th><th>RFQ</th><th>Value</th></tr></thead>
            <tbody>
              {deals.map((deal) => (
                <tr key={deal.id}>
                  <td>{deal.title}<div className="text-xs text-muted">{deal.status}</div></td>
                  <td>{deal.buyer_name || "—"} → {deal.supplier_name || "Unmatched"}</td>
                  <td>{deal.stage}</td>
                  <td>{(deal.rfqs ?? []).length === 0 ? "None" : deal.rfqs.map((rfq) => rfq.status).join(", ")}</td>
                  <td>{deal.pipeline_value} {deal.currency}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </>
  );
}
