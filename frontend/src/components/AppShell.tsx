"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ReactNode } from "react";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "◈", roles: ["admin", "user"] },
  { href: "/templates", label: "Templates",  icon: "⊞", roles: ["admin"] },
  { href: "/validate",  label: "Validate",   icon: "⦿", roles: ["admin", "user"] },
  { href: "/reports",   label: "Reports",    icon: "≡", roles: ["admin", "user"] },
];

function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside style={{
      width: 220, flexShrink: 0,
      background: "#0d1120",
      borderRight: "1px solid #1f2937",
      display: "flex", flexDirection: "column",
    }}>
      {/* Logo */}
      <div style={{ padding: "22px 20px 18px", borderBottom: "1px solid #1f2937" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16, color: "white", fontWeight: 700,
          }}>C</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#f1f5f9", letterSpacing: "-0.3px" }}>ContentGuard</div>
            <div style={{ fontSize: 10, color: "#6b7280" }}>v2.0 · LLM Validation</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      {user && (
        <nav style={{ flex: 1, padding: "12px 10px" }}>
          {NAV.filter(n => n.roles.includes(user.role)).map(n => (
            <Link key={n.href} href={n.href} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "9px 12px", borderRadius: 8, marginBottom: 2,
              color: "#94a3b8", textDecoration: "none", fontSize: 13,
              transition: "all 0.15s",
            }} className="nav-link">
              <span style={{ fontSize: 16, lineHeight: 1 }}>{n.icon}</span>
              <span>{n.label}</span>
            </Link>
          ))}
        </nav>
      )}

      {/* Footer */}
      <div style={{ padding: "14px 16px", borderTop: "1px solid #1f2937" }}>
        {user && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 12, color: "#94a3b8" }}>
              Role: <strong style={{ color: "#f1f5f9" }}>{user.role}</strong>
            </span>
            <button onClick={logout} style={{
              background: "none", border: "none", color: "#ef4444",
              cursor: "pointer", fontSize: 12,
            }}>Logout</button>
          </div>
        )}
        <a href="http://localhost:8000/docs" target="_blank" style={{
          display: "block", fontSize: 11, color: "#6b7280",
          textDecoration: "none", marginBottom: 4,
        }}>📖 API Docs →</a>
        <div style={{ fontSize: 10, color: "#4b5563" }}>MySQL + Python + Next.js</div>
      </div>
    </aside>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  return (
    <AuthProvider>
      <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
        {!isLoginPage && <Sidebar />}
        <main style={{ flex: 1, overflowY: "auto", background: "#0f1117" }}>
          {children}
        </main>
      </div>
    </AuthProvider>
  );
}
