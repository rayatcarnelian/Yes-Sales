"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { ReactNode, useEffect, useState } from "react";

const SHOP = [
  ["/job-cards", "Job cards"],
  ["/approvals", "Approvals"],
];

const EXPORT_DESK = [
  ["/", "Start"],
  ["/companies", "Companies"],
  ["/pipeline/suppliers", "Suppliers"],
  ["/pipeline/buyers", "Buyers"],
  ["/inbox", "Inbox"],
  ["/research", "Grok files"],
  ["/deals", "Deals"],
  ["/agents", "Sales team"],
  ["/audit", "Test record"],
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!window.localStorage.getItem("yes_sales_token")) {
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) return <main className="min-h-screen bg-canvas" />;

  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <aside className="flex flex-col gap-6 bg-[var(--sidebar)] px-5 py-6 text-[var(--sidebar-ink)]">
        <div>
          <p className="font-serif text-2xl tracking-tight">YES SALES</p>
          <p className="mt-1 text-xs text-[var(--gold)]">Your Global Sales Force. Powered by AI.</p>
        </div>
        <nav className="flex flex-1 flex-col gap-4">
          <NavGroup title="Detailing shop" links={SHOP} pathname={pathname} />
          <NavGroup title="Export desk" links={EXPORT_DESK} pathname={pathname} />
        </nav>
        <button className="border border-white/20 px-3 py-2 text-sm" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} type="button">
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
        <button
          className="px-3 py-2 text-left text-sm text-white/70"
          type="button"
          onClick={() => {
            window.localStorage.removeItem("yes_sales_token");
            router.replace("/login");
          }}
        >
          Sign out
        </button>
      </aside>
      <main className="min-w-0 px-5 py-6 md:px-8">{children}</main>
    </div>
  );
}

function NavGroup({ title, links, pathname }: { title: string; links: string[][]; pathname: string }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="px-3 text-xs uppercase tracking-[0.14em] text-[var(--gold)]">{title}</p>
      {links.map(([href, label]) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link key={href} href={href} className={`rounded-full px-3 py-2 text-sm ${active ? "bg-white/10" : "text-white/75"}`}>
            {label}
          </Link>
        );
      })}
    </div>
  );
}

export function PageTitle({ kicker, title, text }: { kicker: string; title: string; text?: string }) {
  return (
    <header className="mb-6">
      <p className="text-xs uppercase tracking-[0.16em] text-[var(--gold)]">{kicker}</p>
      <h1 className="mt-1 font-serif text-4xl">{title}</h1>
      {text ? <p className="mt-2 max-w-2xl text-sm text-muted">{text}</p> : null}
    </header>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-line bg-panel p-4 ${className}`}>{children}</section>;
}

export function ErrorNote({ message }: { message: string }) {
  return message ? <p className="mb-4 text-sm text-[var(--danger)]">{message}</p> : null;
}
