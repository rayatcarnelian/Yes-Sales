"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import { FormEvent, useEffect, useState } from "react";

type Conversation = {
  id: string;
  contact_id: string;
  company_name: string | null;
  contact_name: string | null;
  status: string;
  channel: string;
  subject: string | null;
  latest: { body: string; provider_mode: string; status: string; direction: string; classification: string | null } | null;
};

type Mail = {
  id: string;
  direction: string;
  body: string;
  status: string;
  provider_mode: string;
  classification: string | null;
};

type CallRow = {
  id: string;
  direction: string;
  mode: string;
  provider_mode: string;
  status: string;
  summary: string | null;
};

export default function InboxPage() {
  const [rows, setRows] = useState<Conversation[]>([]);
  const [calls, setCalls] = useState<CallRow[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [messages, setMessages] = useState<Mail[]>([]);
  const [inbound, setInbound] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  function load() {
    api<{ conversations: Conversation[] }>("/conversations").then((data) => setRows(data.conversations)).catch((reason: Error) => setError(reason.message));
    api<{ calls: CallRow[] }>("/calls").then((data) => setCalls(data.calls)).catch((reason: Error) => setError(reason.message));
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!selected) return;
    api<{ messages: Mail[] }>(`/conversations/${selected}/messages`).then((data) => setMessages(data.messages)).catch((reason: Error) => setError(reason.message));
  }, [selected]);

  const current = rows.find((row) => row.id === selected);

  async function onDraft(event: FormEvent) {
    event.preventDefault();
    if (!current) return;
    setError("");
    setNotice("");
    try {
      const draft = await api<{ sent: boolean; message: Mail; approval: { status: string } }>("/alex/drafts", {
        method: "POST",
        body: JSON.stringify({ contact_id: current.contact_id, subject: current.subject, body: inbound }),
      });
      setNotice(`Draft stored. Sent: ${String(draft.sent)}. Approval: ${draft.approval.status}. Provider: ${draft.message.provider_mode}.`);
      setInbound("");
      const thread = await api<{ messages: Mail[] }>(`/conversations/${selected}/messages`);
      setMessages(thread.messages);
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Draft failed");
    }
  }

  async function handoff() {
    if (!selected) return;
    setError("");
    try {
      await api(`/conversations/${selected}/handoff`, { method: "POST", body: JSON.stringify({ note: "Person requested from inbox" }) });
      setNotice("Conversation marked for human handoff. No call was placed.");
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Handoff failed");
    }
  }

  return (
    <>
      <PageTitle kicker="Alex" title="Inbox" text="Drafts stay unsent until a founder approves them. Email is mocked until SMTP is configured. No live call has been verified." />
      <ErrorNote message={error} />
      {notice ? <p className="mb-4 text-sm text-ink">{notice}</p> : null}
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div className="grid gap-3">
          {rows.length === 0 ? <Panel><p className="text-sm text-muted">No conversations yet.</p></Panel> : rows.map((row) => (
            <button key={row.id} className="rounded-2xl border border-line bg-panel p-4 text-left" onClick={() => setSelected(row.id)} type="button">
              <span className="block font-medium">{row.company_name} · {row.contact_name}</span>
              <span className="mt-1 block text-xs uppercase text-muted">{row.status} · {row.channel}</span>
            </button>
          ))}
        </div>
        <Panel>
          {current ? (
            <>
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-medium">{current.subject || "No subject"}</h2>
                <button className="rounded-full border border-line px-3 py-1 text-sm" onClick={handoff} type="button">Hand to a person</button>
              </div>
              <div className="mt-4 grid gap-3">
                {messages.map((item) => (
                  <article key={item.id} className="rounded-xl border border-line p-3">
                    <p className="text-xs uppercase text-muted">{item.direction} · {item.status} · {item.provider_mode} · {item.classification || "unclassified"}</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm">{item.body}</p>
                  </article>
                ))}
              </div>
              <form className="mt-4 grid gap-3" onSubmit={onDraft}>
                <textarea className="min-h-24 rounded-xl border border-line bg-canvas px-3 py-2 text-sm" placeholder="Inbound text to classify and draft from" value={inbound} onChange={(event) => setInbound(event.target.value)} required />
                <button className="w-fit rounded-full bg-accent px-4 py-2 text-sm text-white" type="submit">Create unsent draft</button>
              </form>
            </>
          ) : <p className="text-sm text-muted">Select a conversation. Creating a draft does not send it.</p>}
        </Panel>
      </div>
      <h2 className="mb-3 mt-8 font-medium">Call outcomes</h2>
      <div className="grid gap-3">
        {calls.length === 0 ? <Panel><p className="text-sm text-muted">No calls stored. Live calling is not verified.</p></Panel> : calls.map((call) => (
          <Panel key={call.id}>
            <p className="text-xs uppercase text-muted">{call.direction} · {call.mode} · {call.status} · {call.provider_mode}</p>
            <p className="mt-2 text-sm">{call.summary}</p>
          </Panel>
        ))}
      </div>
    </>
  );
}