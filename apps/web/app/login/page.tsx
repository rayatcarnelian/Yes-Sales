"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [localHint, setLocalHint] = useState(false);

  useEffect(() => {
    const host = window.location.hostname;
    const local = host === "localhost" || host === "127.0.0.1";
    setLocalHint(local);
    if (local) setEmail("founder@yes-sales.test");
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await response.json();
    if (!response.ok) {
      setError(data?.error?.message || "Login failed");
      return;
    }
    window.localStorage.setItem("yes_sales_token", data.access_token);
    router.replace("/");
  }

  return (
    <main className="grid min-h-screen place-items-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-md rounded-3xl border border-line bg-panel p-8">
        <p className="font-serif text-4xl">YES SALES</p>
        <p className="mt-2 text-sm text-muted">Your Global Sales Force. Powered by AI.</p>
        {localHint ? (
          <p className="mt-4 rounded-2xl border border-line px-3 py-2 text-sm text-muted">
            This machine only. Founder: founder@yes-sales.test / change-me-founder. Operator: operator@yes-sales.test / change-me-operator.
          </p>
        ) : null}
        <label className="mt-6 block text-sm">Email<input className="mt-1" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label className="mt-4 block text-sm">Password<input className="mt-1" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {error ? <p className="mt-3 text-sm text-[var(--danger)]">{error}</p> : null}
        <button className="mt-6 bg-accent px-5 py-2 text-sm text-[var(--accent-ink)]" type="submit">Enter command center</button>
      </form>
    </main>
  );
}
