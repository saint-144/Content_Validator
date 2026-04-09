import type { Metadata } from "next";
import "../styles/globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "ContentGuard – Validation Platform",
  description: "LLM-powered content validation against trained templates",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppShell>
          {children}
        </AppShell>
        <style>{`
          .nav-link:hover { color: #e2e8f0 !important; background: #1c2333 !important; }
        `}</style>
      </body>
    </html>
  );
}
