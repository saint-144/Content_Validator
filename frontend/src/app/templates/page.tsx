'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getTemplates, createTemplate, deleteTemplate, type Template } from '@/lib/api';
import { format } from 'date-fns';

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const load = () => getTemplates().then(setTemplates).catch(() => setError('API unreachable')).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await createTemplate(name.trim(), desc.trim() || undefined);
      setName(''); setDesc(''); setShowCreate(false);
      load();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Create failed');
    } finally { setCreating(false); }
  };

  const handleDelete = async (t: Template) => {
    if (!confirm(`Delete template "${t.name}"? This will remove all ${t.file_count} trained files.`)) return;
    await deleteTemplate(t.id);
    load();
  };

  const statusBadge = (s: string) => <span className={`badge badge-${s}`}>{s.charAt(0).toUpperCase()+s.slice(1)}</span>;

  return (
    <div style={{ padding:28 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:24 }}>
        <div>
          <h1 style={{ fontSize:22, fontWeight:700, color:'#f1f5f9' }}>Templates</h1>
          <p style={{ fontSize:13, color:'#6b7280', marginTop:3 }}>
            Each template is a named batch of approved content files trained for validation
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          + Create Template
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="card" style={{ padding:20, marginBottom:20 }}>
          <h3 style={{ fontSize:14, fontWeight:600, color:'#e2e8f0', marginBottom:14 }}>New Template</h3>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginBottom:14 }}>
            <div>
              <label className="label">Template Name *</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)}
                placeholder="e.g. Q1 2024 Campaign" onKeyDown={e => e.key === 'Enter' && handleCreate()} />
            </div>
            <div>
              <label className="label">Description</label>
              <input className="input" value={desc} onChange={e => setDesc(e.target.value)}
                placeholder="Optional description" />
            </div>
          </div>
          {error && <div style={{ color:'#ef4444', fontSize:12, marginBottom:10 }}>{error}</div>}
          <div style={{ display:'flex', gap:10 }}>
            <button className="btn-primary" onClick={handleCreate} disabled={!name.trim() || creating}>
              {creating ? 'Creating...' : 'Create Template'}
            </button>
            <button className="btn-secondary" onClick={() => { setShowCreate(false); setError(''); }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Templates grid */}
      {loading ? (
        <div style={{ textAlign:'center', padding:40, color:'#6b7280' }}>Loading templates...</div>
      ) : templates.length === 0 ? (
        <div className="card" style={{ padding:48, textAlign:'center' }}>
          <div style={{ fontSize:40, marginBottom:12 }}>⊞</div>
          <div style={{ fontSize:15, color:'#e2e8f0', marginBottom:6 }}>No templates yet</div>
          <div style={{ fontSize:13, color:'#6b7280', marginBottom:16 }}>
            Create a template and upload approved content files to start validating
          </div>
          <button className="btn-primary" onClick={() => setShowCreate(true)}>+ Create First Template</button>
        </div>
      ) : (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))', gap:14 }}>
          {templates.map(t => (
            <div key={t.id} className="card" style={{ padding:20 }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:10 }}>
                <div style={{ fontSize:15, fontWeight:600, color:'#f1f5f9' }}>{t.name}</div>
                {statusBadge(t.status)}
              </div>
              {t.description && (
                <div style={{ fontSize:12, color:'#6b7280', marginBottom:10 }}>{t.description}</div>
              )}
              <div style={{ display:'flex', gap:16, fontSize:12, color:'#94a3b8', marginBottom:14 }}>
                <span>📁 {t.file_count} files</span>
                {t.trained_at && <span>✓ Trained {format(new Date(t.trained_at), 'MMM d')}</span>}
                <span style={{ color:'#4b5563' }}>Created {format(new Date(t.created_at), 'MMM d')}</span>
              </div>
              <div style={{ display:'flex', gap:8 }}>
                <Link href={`/templates/${t.id}`}>
                  <button className="btn-primary" style={{ fontSize:12, padding:'7px 14px' }}>
                    Manage Files
                  </button>
                </Link>
                <button onClick={() => handleDelete(t)}
                  style={{ background:'transparent', border:'1px solid #374151', color:'#9ca3af',
                    padding:'7px 12px', borderRadius:7, fontSize:12, cursor:'pointer' }}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
