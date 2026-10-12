"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Backtest" },
  { href: "/paper", label: "Paper trading" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="mb-6 flex gap-5 text-sm">
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={pathname === link.href ? "font-semibold text-emerald-400" : "text-slate-400 hover:text-slate-200"}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
