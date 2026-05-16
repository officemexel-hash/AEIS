"use client";

import Link from "next/link";
import { ArrowRight, Menu, X } from "lucide-react";
import { useState } from "react";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen" style={{ background: "#050816" }}>
      {/* Nav */}
      <nav className="fixed top-0 inset-x-0 z-50 h-16 border-b backdrop-blur-xl"
        style={{
          background: "rgba(5, 8, 22, 0.85)",
          borderColor: "rgba(148, 163, 184, 0.08)",
        }}
      >
        <div className="max-w-7xl mx-auto h-full flex items-center justify-between px-6 md:px-12">
          <Link href="/" className="flex items-center gap-3 group">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{
                background: "linear-gradient(135deg, #2F6BFF, #1a4fd4)",
                boxShadow: "0 0 20px rgba(47, 107, 255, 0.25)",
              }}
            >
              <span className="text-white font-bold text-sm">S</span>
            </div>
            <span className="text-sm font-semibold tracking-widest uppercase"
              style={{ color: "#E2E8F0" }}
            >
              SYLION AEIS
            </span>
          </Link>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-8">
            <a href="#what" className="text-xs tracking-wide transition-colors"
              style={{ color: "#94A3B8" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#E2E8F0")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#94A3B8")}
            >
              Platform
            </a>
            <a href="#capabilities" className="text-xs tracking-wide transition-colors"
              style={{ color: "#94A3B8" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#E2E8F0")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#94A3B8")}
            >
              Capabilities
            </a>
            <a href="#architecture" className="text-xs tracking-wide transition-colors"
              style={{ color: "#94A3B8" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#E2E8F0")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#94A3B8")}
            >
              Architecture
            </a>
            <a href="#governance" className="text-xs tracking-wide transition-colors"
              style={{ color: "#94A3B8" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#E2E8F0")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#94A3B8")}
            >
              Governance
            </a>
            <a href="#use-cases" className="text-xs tracking-wide transition-colors"
              style={{ color: "#94A3B8" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#E2E8F0")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "#94A3B8")}
            >
              Use Cases
            </a>
            <Link
              href="/overview"
              className="flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-semibold transition-all"
              style={{
                background: "#2F6BFF",
                color: "#fff",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = "0 0 24px rgba(47, 107, 255, 0.4)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              Launch Console <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden"
            style={{ color: "#94A3B8" }}
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div
            className="md:hidden border-t px-6 py-4 space-y-3"
            style={{
              background: "rgba(5, 8, 22, 0.95)",
              borderColor: "rgba(148, 163, 184, 0.08)",
            }}
          >
            {[
              { href: "#what", label: "Platform" },
              { href: "#capabilities", label: "Capabilities" },
              { href: "#architecture", label: "Architecture" },
              { href: "#governance", label: "Governance" },
              { href: "#use-cases", label: "Use Cases" },
            ].map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="block text-sm py-1"
                style={{ color: "#94A3B8" }}
                onClick={() => setMobileOpen(false)}
              >
                {item.label}
              </a>
            ))}
            <Link
              href="/overview"
              className="flex items-center gap-2 text-sm font-semibold pt-2"
              style={{ color: "#2F6BFF" }}
              onClick={() => setMobileOpen(false)}
            >
              Launch Console <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        )}
      </nav>

      {/* Page content */}
      <main>{children}</main>
    </div>
  );
}
