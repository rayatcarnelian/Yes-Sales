"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import { FormEvent, use, useEffect, useState } from "react";

type Profile = {
  company: {
    id: string;
    legal_name: string;
    country: string;
    role: string;
    verification_status: string;
    supplier_stage: string | null;
    buyer_stage: string | null;
    summary: string | null;
    website: string | null;
  };
  contacts: Array<{ id: string; full_name: string; channel: string; value: string; permission?: { allowed: boolean; opted_out: boolean } }>;
  sources: Array<{ id: string; source_url: string; retrieved_at: string; excerpt: string; provider_mode: string }>;
  requirements: Array<{ id: string; product_category: string }>;
  activity: Array<{ id: string; action: string; created_at: string }>;
  next_supplier_stage: string | null;
  next_buyer_stage: string | null;
};

export default function CompanyProfile({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [contact, setContact] = useState({ full_name: "", value: "", allowed: false });
  const [excerpt, setExcerpt] = useState("Company: \nCategory: ");
  const [sourceUrl, setSourceUrl] = useState("https://");

  function load(companyId: string) {
    api<Profile>(`/companies/${companyId}`).then(setProfile).catch((reason: Error) => setError(reason.message));
  }

  useEffect(() => {
    if (id) load(id);
  }, [id]);

  async function addContact(event: FormEvent) {
    event.preventDefault();
    try {
      await api(`/companies/${id}/contacts`, { method: "POST", body: JSON.stringify({ ...contact, channel: "email", authorization_basis: contact.allowed ? "explicit_consent" : "unknown" }) });
      setContact({ full_name: "", value: "", allowed: false });
      load(id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Contact was not saved");
    }
  }

  async function addSource(event: FormEvent) {
    event.preventDefault();
    try {
      await api("/research/sources", { method: "POST", body: JSON.stringify({ company_id: id, source_url: sourceUrl, excerpt, provider: "manual" }) });
      load(id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Source was not saved");
    }
  }

  async function advance(side: "supplier" | "buyer", stage: string | null) {
    if (!stage) return;
    try {
      await api(`/companies/${id}/transitions`, { method: "POST", body: JSON.stringify({ side, to_stage: stage }) });
      load(id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Transition was rejected");
    }
  }

  if (!profile) return <p className="text-sm text-muted">Loading profile…</p>;

  return (
    <>
      <PageTitle kicker={`${profile.company.country} · ${profile.company.role}`} title={profile.company.legal_name} text={profile.company.summary || profile.company.website || "No summary stored."} />
      <ErrorNote message={error} />
      <div className="mb-4 flex flex-wrap gap-2 text-sm">
        <span className="rounded-full border border-line px-3 py-1">Verification {profile.company.verification_status}</span>
        <span className="rounded-full border border-line px-3 py-1">Supplier {profile.company.supplier_stage || "—"}</span>
        <span className="rounded-full border border-line px-3 py-1">Buyer {profile.company.buyer_stage || "—"}</span>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <h2 className="font-medium">Contacts</h2>
          {profile.contacts.length === 0 ? <p className="mt-2 text-sm text-muted">No contacts stored.</p> : profile.contacts.map((item) => (
            <p key={item.id} className="mt-2 text-sm">{item.full_name} · {item.channel} · {item.value} · {item.permission?.opted_out ? "opted out" : item.permission?.allowed ? "eligible" : "not eligible"}</p>
          ))}
          <form onSubmit={addContact} className="mt-4 grid gap-2">
            <input placeholder="Name" value={contact.full_name} onChange={(event) => setContact({ ...contact, full_name: event.target.value })} required />
            <input placeholder="Email" value={contact.value} onChange={(event) => setContact({ ...contact, value: event.target.value })} required />
            <label className="flex items-center gap-2 text-sm"><input className="w-auto" type="checkbox" checked={contact.allowed} onChange={(event) => setContact({ ...contact, allowed: event.target.checked })} /> Allowed to contact</label>
            <button className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" type="submit">Save contact</button>
          </form>
        </Panel>
        <Panel>
          <h2 className="font-medium">Source evidence</h2>
          <p className="mt-1 text-sm text-muted">A bot claim is not a source. This list shows only excerpts recorded here.</p>
          {profile.sources.length === 0 ? <p className="mt-2 text-sm text-muted">No sources stored.</p> : profile.sources.map((source) => (
            <article key={source.id} className="mt-3 text-sm">
              <a className="underline" href={source.source_url}>{source.source_url}</a>
              <p className="text-xs text-muted">{source.retrieved_at} · {source.provider_mode}</p>
              <p className="mt-1 whitespace-pre-wrap">{source.excerpt}</p>
            </article>
          ))}
          <form onSubmit={addSource} className="mt-4 grid gap-2">
            <input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} required />
            <textarea rows={4} value={excerpt} onChange={(event) => setExcerpt(event.target.value)} />
            <button className="border border-line px-4 py-2 text-sm" type="submit">Record source</button>
          </form>
        </Panel>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="border border-line px-4 py-2 text-sm" type="button" disabled={!profile.next_supplier_stage} onClick={() => advance("supplier", profile.next_supplier_stage)}>Advance supplier to {profile.next_supplier_stage || "end"}</button>
        <button className="border border-line px-4 py-2 text-sm" type="button" disabled={!profile.next_buyer_stage} onClick={() => advance("buyer", profile.next_buyer_stage)}>Advance buyer to {profile.next_buyer_stage || "end"}</button>
      </div>
      {profile.requirements.length > 0 ? <Panel className="mt-4"><h2 className="font-medium">Requirements</h2>{profile.requirements.map((item) => <p key={item.id} className="mt-2 text-sm">{item.product_category}</p>)}</Panel> : null}
      <Panel className="mt-4">
        <h2 className="font-medium">Contact activity</h2>
        {profile.activity.length === 0 ? <p className="mt-2 text-sm text-muted">No contact activity recorded.</p> : profile.activity.map((item) => (
          <p key={item.id} className="mt-2 text-sm">{item.action}<span className="text-muted"> · {item.created_at}</span></p>
        ))}
      </Panel>
    </>
  );
}
