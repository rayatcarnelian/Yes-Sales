"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

type Company = {
  id: string;
  legal_name: string;
  country: string;
  role: string;
  verification_status: string;
  category: string | null;
  supplier_stage: string | null;
  buyer_stage: string | null;
  is_test: boolean;
};

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({ legal_name: "", country: "BD", role: "supplier", category: "", website: "", is_test: true });

  function load(q = query) {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    api<{ companies: Company[] }>(`/companies?${params.toString()}`)
      .then((data) => setCompanies(data.companies))
      .catch((reason: Error) => setError(reason.message));
  }

  useEffect(() => {
    load("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createCompany(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/companies", { method: "POST", body: JSON.stringify({ ...form, category: form.category || null, website: form.website || null }) });
      setForm({ ...form, legal_name: "", website: "" });
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create company");
    }
  }

  return (
    <>
      <PageTitle kicker="CRM" title="Companies" text="Search stored companies. New records stay unverified until a source is attached." />
      <ErrorNote message={error} />
      <Panel>
        <form onSubmit={createCompany} className="grid gap-3 md:grid-cols-3">
          <input placeholder="Legal name" value={form.legal_name} onChange={(event) => setForm({ ...form, legal_name: event.target.value })} required />
          <input placeholder="Country" value={form.country} maxLength={2} onChange={(event) => setForm({ ...form, country: event.target.value.toUpperCase() })} required />
          <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
            <option value="supplier">Supplier</option>
            <option value="buyer">Buyer</option>
            <option value="both">Both</option>
          </select>
          <input placeholder="Category" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} />
          <input placeholder="Website" value={form.website} onChange={(event) => setForm({ ...form, website: event.target.value })} />
          <button className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" type="submit">Create company</button>
        </form>
      </Panel>
      <Panel className="mt-4">
        <form className="mb-4 flex gap-2" onSubmit={(event) => { event.preventDefault(); load(); }}>
          <input placeholder="Search legal name" value={query} onChange={(event) => setQuery(event.target.value)} />
          <button className="border border-line px-4 py-2 text-sm" type="submit">Search</button>
        </form>
        {companies.length === 0 ? <p className="text-sm text-muted">No companies stored yet.</p> : (
          <table>
            <thead><tr><th>Name</th><th>Role</th><th>Stage</th><th>Verification</th></tr></thead>
            <tbody>
              {companies.map((company) => (
                <tr key={company.id}>
                  <td><Link className="underline" href={`/companies/${company.id}`}>{company.legal_name}</Link>{company.is_test ? " · TEST" : ""}<div className="text-xs text-muted">{company.country} · {company.category || "Uncategorized"}</div></td>
                  <td>{company.role}</td>
                  <td>{company.supplier_stage || company.buyer_stage}</td>
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
