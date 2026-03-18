import type { Metadata } from 'next';
import Link from 'next/link';
import '../styles/globals.css';

export const metadata: Metadata = {
  title: 'ContentGuard – Validation Platform',
  description: 'LLM-powered content validation against trained templates',
};

const NAV = [
  { href: '/dashboard',  label: 'Dashboard',  icon: '◈' },
  { href: '/templates',  label: 'Templates',  icon: '⊞' },
  { href: '/validate',   label: 'Validate',   icon: '⦿' },
  { href: '/reports',    label: 'Reports',    icon: '≡' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div style={{ display:'flex', height:'100vh', overflow:'hidden' }}>
          {/* Sidebar */}
          <aside style={{
            width: 220, flexShrink: 0,
            background: '#0d1120',
            borderRight: '1px solid #1f2937',
            display: 'flex', flexDirection: 'column',
          }}>
            {/* Logo */}
            <div style={{ padding: '22px 20px 18px', borderBottom: '1px solid #1f2937' }}>
              <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: 8,
                  background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                  display:'flex', alignItems:'center', justifyContent:'center',
                  fontSize: 16, color:'white', fontWeight:700
                }}>C</div>
                <div>
                  <div style={{ fontSize:14, fontWeight:700, color:'#f1f5f9', letterSpacing:'-0.3px' }}>ContentGuard</div>
                  <div style={{ fontSize:10, color:'#6b7280' }}>v2.0 · LLM Validation</div>
                </div>
              </div>
            </div>

            {/* Nav */}
            <nav style={{ flex:1, padding: '12px 10px' }}>
              {NAV.map(n => (
                <Link key={n.href} href={n.href} style={{
                  display:'flex', alignItems:'center', gap: 10,
                  padding: '9px 12px', borderRadius: 8, marginBottom: 2,
                  color: '#94a3b8', textDecoration: 'none', fontSize: 13,
                  transition: 'all 0.15s',
                }}
                className="nav-link">
                  <span style={{ fontSize:16, lineHeight:1 }}>{n.icon}</span>
                  <span>{n.label}</span>
                </Link>
              ))}
            </nav>

            {/* Footer */}
            <div style={{ padding: '14px 16px', borderTop: '1px solid #1f2937' }}>
              <a href="http://localhost:8000/docs" target="_blank" style={{
                display:'block', fontSize:11, color:'#6b7280',
                textDecoration:'none', marginBottom:4
              }}>📖 API Docs →</a>
              <div style={{ fontSize:10, color:'#4b5563' }}>MySQL + Python + Next.js</div>
            </div>
          </aside>

          {/* Main */}
          <main style={{ flex:1, overflowY:'auto', background:'#0f1117' }}>
            {children}
          </main>
        </div>

        <style>{`
          .nav-link:hover { color: #e2e8f0 !important; background: #1c2333 !important; }
        `}</style>
      </body>
    </html>
  );
}
