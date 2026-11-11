"use client";

import { ErrorNote, PageTitle, Panel } from "@/components/shell";
import { api } from "@/lib/api";
import { FormEvent, useEffect, useState } from "react";

type Reply = {
  id: string;
  body: string;
  sent: boolean;
  price_allowed: boolean;
};

type JobCard = {
  id: string;
  company_id: string;
  vehicle: string;
  requested_service: string;
  preferred_time: string | null;
  status: string;
  bay_confirmed: boolean;
  replies: Reply[];
};

type Company = { id: string; legal_name: string; country: string };
type Sheet = { id: string; company_id: string; service_name: string; price: string; currency: string; status: string; allowed_sentence: string };
type Me = { role: string; full_name: string };

function cardLabel(row: JobCard): string {
  if (row.bay_confirmed || row.status === "bay_confirmed") return "Bay confirmed by you";
  if (row.status === "handed_off") return "Needs a person";
  if (row.status === "declined") return "Declined";
  if (row.status === "price_approved") return "Price approved";
  return "Request saved. Bay not booked.";
}

function moneySentence(name: string, price: string): string {
  return `${name.trim()} is RM${price}.`;
}

export default function JobCardsPage() {
  const [rows, setRows] = useState<JobCard[]>([]);
  const [shops, setShops] = useState<Company[]>([]);
  const [sheets, setSheets] = useState<Sheet[]>([]);
  const [me, setMe] = useState<Me | null>(null);
  const [shopId, setShopId] = useState("");
  const [shopName, setShopName] = useState("");
  const [serviceName, setServiceName] = useState("");
  const [price, setPrice] = useState("");
  const [vehicle, setVehicle] = useState("");
  const [requested, setRequested] = useState("");
  const [when, setWhen] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");

  const shopSheets = sheets.filter((sheet) => sheet.company_id === shopId);
  const approved = shopSheets.filter((sheet) => sheet.status === "approved");
  const sentence = serviceName.trim() && /^\d+(\.\d{1,2})?$/.test(price) ? moneySentence(serviceName, price) : "";

  function load() {
    return Promise.all([
      api<{ job_cards: JobCard[] }>("/job-cards"),
      api<{ companies: Company[] }>("/companies?role=supplier"),
      api<{ service_sheets: Sheet[] }>("/service-sheets"),
      api<Me>("/me"),
    ]).then(([cards, companies, menu, user]) => {
      setRows(cards.job_cards);
      setShops(companies.companies);
      setSheets(menu.service_sheets);
      setMe(user);
      setShopId((current) => current || companies.companies[0]?.id || "");
    });
  }

  useEffect(() => {
    load().catch((reason: Error) => setError(reason.message));
  }, []);

  async function run(label: string, work: () => Promise<void>) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await work();
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "That step failed. Nothing was sent.");
    } finally {
      setBusy("");
    }
  }

  function addShop(event: FormEvent) {
    event.preventDefault();
    const legalName = shopName.trim();
    if (legalName.length < 2) {
      setError("Enter the shop name.");
      return;
    }
    void run("shop", async () => {
      const created = await api<Company>("/companies", {
        method: "POST",
        body: JSON.stringify({ legal_name: legalName, country: "MY", role: "supplier", category: "Detailing", is_test: false }),
      });
      setShopName("");
      setShopId(created.id);
      setNotice(`${created.legal_name} is on the desk. Add a price next.`);
    });
  }

  function approvePrice(event: FormEvent) {
    event.preventDefault();
    if (!shopId) {
      setError("Choose a shop first.");
      return;
    }
    if (!sentence) {
      setError("Enter a service name and a price such as 450 or 450.00.");
      return;
    }
    void run("price", async () => {
      const sheet = await api<Sheet>("/service-sheets", {
        method: "POST",
        body: JSON.stringify({
          company_id: shopId,
          service_name: serviceName.trim(),
          currency: "MYR",
          price,
          allowed_sentence: sentence,
          duration_notes: "Entered on the job card desk",
        }),
      });
      const approval = await api<{ id: string }>(`/service-sheets/${sheet.id}/request-approval`, { method: "POST" });
      await api(`/approvals/${approval.id}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision: "approved", note: "Approved on the job card desk" }),
      });
      await api(`/approvals/${approval.id}/execute`, { method: "POST" });
      setServiceName("");
      setPrice("");
      setRequested(sheet.service_name);
      setNotice(`Approved. The assistant may say “${sentence}” and no other price.`);
    });
  }

  function fileCard(event: FormEvent) {
    event.preventDefault();
    if (!shopId || vehicle.trim().length < 2 || requested.trim().length < 2 || message.trim().length < 1) {
      setError("Choose the shop, then enter the car, the package, and what the customer said.");
      return;
    }
    void run("card", async () => {
      const filed = await api<JobCard & { reply: Reply }>("/job-cards", {
        method: "POST",
        body: JSON.stringify({
          company_id: shopId,
          vehicle: vehicle.trim(),
          requested_service: requested.trim(),
          preferred_time: when.trim() || null,
          customer_message: message.trim(),
        }),
      });
      setVehicle("");
      setWhen("");
      setMessage("");
      const reply = filed.reply;
      setNotice(reply.price_allowed ? "Request saved. The draft repeats an approved price. It was not sent." : "Request saved. The draft states no price. It was not sent.");
    });
  }

  return (
    <>
      <PageTitle
        kicker="Owner"
        title="Job cards"
        text="Three steps. Add the shop, approve a price, then save the car and the customer's words. A draft can repeat only a price you approved. The bay stays unbooked, and nothing is sent."
      />
      <ErrorNote message={error} />
      {notice ? <p className="mb-4 text-sm text-[var(--ok)]">{notice}</p> : null}
      <p className="mb-4 text-sm text-muted">{me ? `Signed in as ${me.full_name} (${me.role}). Only a founder can approve a price.` : "Loading your shops."}</p>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <h2 className="font-medium">1. Shop</h2>
          <label className="mt-3 block text-sm">
            Choose a shop
            <select className="mt-1" value={shopId} onChange={(event) => setShopId(event.target.value)}>
              {shops.length === 0 ? <option value="">No shop yet</option> : null}
              {shops.map((shop) => (
                <option key={shop.id} value={shop.id}>{shop.legal_name}</option>
              ))}
            </select>
          </label>
          <form className="mt-4" onSubmit={addShop}>
            <label className="block text-sm">
              Or add a shop
              <input className="mt-1" value={shopName} onChange={(event) => setShopName(event.target.value)} placeholder="Shop name" />
            </label>
            <button className="mt-3 bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" disabled={busy !== ""} type="submit">
              {busy === "shop" ? "Saving…" : "Add shop"}
            </button>
          </form>
        </Panel>

        <Panel>
          <h2 className="font-medium">2. Price the assistant may say</h2>
          <form className="mt-3 grid gap-3" onSubmit={approvePrice}>
            <label className="text-sm">
              Service
              <input className="mt-1" value={serviceName} onChange={(event) => setServiceName(event.target.value)} placeholder="interior detail" />
            </label>
            <label className="text-sm">
              Price in RM
              <input className="mt-1" inputMode="decimal" value={price} onChange={(event) => setPrice(event.target.value.trim())} placeholder="450" />
            </label>
            <p className="text-sm text-muted">{sentence ? `Allowed sentence: ${sentence}` : "Enter a name and a number. The sentence is built for you, so the draft cannot add a second amount."}</p>
            <button className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" disabled={busy !== ""} type="submit">
              {busy === "price" ? "Approving…" : "Approve this price"}
            </button>
          </form>
          <ul className="mt-4 grid gap-2">
            {shopSheets.length === 0 ? <li className="text-sm text-muted">No prices for this shop yet.</li> : shopSheets.map((sheet) => (
              <li key={sheet.id} className="text-sm">
                <span className="font-medium">{sheet.service_name}</span>
                <span className="text-muted"> · {sheet.status === "approved" ? "Approved" : "Draft, cannot be quoted"} · {sheet.allowed_sentence}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel className="mt-4">
        <h2 className="font-medium">3. Save a request</h2>
        <form className="mt-3 grid gap-3 md:grid-cols-2" onSubmit={fileCard}>
          <label className="text-sm">
            Car
            <input className="mt-1" value={vehicle} onChange={(event) => setVehicle(event.target.value)} placeholder="Myvi, silver" />
          </label>
          <label className="text-sm">
            Package
            <input className="mt-1" list="approved-services" value={requested} onChange={(event) => setRequested(event.target.value)} placeholder="interior detail" />
            <datalist id="approved-services">
              {approved.map((sheet) => <option key={sheet.id} value={sheet.service_name} />)}
            </datalist>
          </label>
          <label className="text-sm">
            Preferred time
            <input className="mt-1" value={when} onChange={(event) => setWhen(event.target.value)} placeholder="Tomorrow morning" />
          </label>
          <label className="text-sm md:col-span-2">
            What the customer said
            <textarea className="mt-1" rows={3} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="How much is interior detail?" />
          </label>
          <div>
            <button className="bg-accent px-4 py-2 text-sm text-[var(--accent-ink)]" disabled={busy !== ""} type="submit">
              {busy === "card" ? "Saving…" : "Save request"}
            </button>
          </div>
        </form>
      </Panel>

      <div className="mt-4 grid gap-3">
        {rows.length === 0 ? (
          <Panel><p className="text-sm text-muted">No requests yet.</p></Panel>
        ) : rows.map((row) => {
          const reply = row.replies[0];
          const shop = shops.find((item) => item.id === row.company_id);
          return (
            <Panel key={row.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="font-medium">{row.vehicle}</h2>
                  <p className="text-sm text-muted">
                    {shop ? `${shop.legal_name} · ` : ""}
                    {row.requested_service}
                    {row.preferred_time ? ` · ${row.preferred_time}` : ""}
                  </p>
                </div>
                <p className="text-sm">{reply?.price_allowed ? "Price allowed" : "No price in the draft"}</p>
              </div>
              <p className="mt-3 text-sm">{reply ? reply.body : "No draft yet."}</p>
              <p className="mt-2 text-sm text-muted">{cardLabel(row)} Draft only. Not sent.</p>
            </Panel>
          );
        })}
      </div>
    </>
  );
}
