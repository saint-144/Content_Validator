'use client';
import { useEffect, useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useParams, useRouter } from 'next/navigation';
import { getTemplate, uploadTemplateFiles, retrainTemplate, deleteTemplateFile, type TemplateDetail, type TemplateFile } from '@/lib/api';
import { format } from 'date-fns';

const STATUS_ICON: Record<string, string> = { done:'✅', processing:'⟳', pending:'⏳', error:'❌' };

function FileRow({ tf, onDelete }: { tf: TemplateFile; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr>
        <td>
          <span style={{ fontSize:16 }}>{tf.file_type === 'video' ? '🎬' : '🖼️'}</span>
        </td>
        <td style={{ maxWidth:220, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
          {tf.original_name}
        </td>
        <td>{(tf.file_size_bytes ? (tf.file_size_bytes/1024).toFixed(0) : '—') + ' KB'}</td>
        <td>
          <span className={`badge badge-${tf.processing_status}`}>
            <span className={tf.processing_status === 'processing' ? 'spin' : ''}>
              {STATUS_ICON[tf.processing_status]}
            </span>
            {' '}{tf.processing_status}
          </span>
        </td>
        <td style={{ maxWidth:280, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', color:'#94a3b8', fontSize:12 }}>
          {tf.llm_summary || (tf.processing_status === 'pending' ? 'Awaiting training...' : '—')}
        </td>
        <td style={{ color:'#6b7280', fontSize:12 }}>{format(new Date(tf.created_at), 'MM/dd HH:mm')}</td>
        <td>
          <div style={{ display:'flex', gap:6 }}>
            {tf.llm_summary && (
              <button onClick={() => setExpanded(!expanded)}
                style={{ background:'transparent', border:'1px solid #374151', color:'#94a3b8',
                  padding:'4px 8px', borderRadius:5, fontSize:11, cursor:'pointer' }}>
                {expanded ? 'Less' : 'Details'}
              </button>
            )}
            <button onClick={onDelete}
              style={{ background:'transparent', border:'1px solid #374151', color:'#ef4444',
                padding:'4px 8px', borderRadius:5, fontSize:11, cursor:'pointer' }}>✕</button>
          </div>
        </td>
      </tr>
      {expanded && tf.llm_summary && (
        <tr>
          <td colSpan={7} style={{ background:'#0f1117', padding:'12px 16px' }}>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, fontSize:12 }}>
              <div>
                <div style={{ color:'#6b7280', marginBottom:4 }}>LLM Summary</div>
                <div style={{ color:'#d1d5db', lineHeight:1.6 }}>{tf.llm_summary}</div>
              </div>
              <div>
                {tf.detected_text && (
                  <>
                    <div style={{ color:'#6b7280', marginBottom:4 }}>Detected Text</div>
                    <div style={{ color:'#d1d5db', fontFamily:'monospace', background:'#161b27',
                      padding:8, borderRadius:6, maxHeight:80, overflow:'auto' }}>
                      {tf.detected_text}
                    </div>
                  </>
                )}
                {tf.visual_elements && typeof tf.visual_elements === 'object' && (
                  <>
                    <div style={{ color:'#6b7280', marginTop:8, marginBottom:4 }}>Visual Elements</div>
                    <div style={{ color:'#94a3b8' }}>
                      {Array.isArray(tf.visual_elements)
                        ? tf.visual_elements.join(', ')
                        : (tf.visual_elements as any).visual_elements?.join(', ') || '—'}
                    </div>
                  </>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function TemplateDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [retraining, setRetraining] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');

  const load = useCallback(() => {
    getTemplate(id).then(setTemplate).catch(() => setError('Failed to load template')).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000); // Poll for training status
    return () => clearInterval(interval);
  }, [load]);

  const onDrop = useCallback((accepted: File[]) => {
    setPendingFiles(prev => [...prev, ...accepted]);
    setError('');
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': [], 'video/*': [] },
    maxSize: 100 * 1024 * 1024
  });

  const handleUpload = async () => {
    if (!pendingFiles.length) return;
    setUploading(true); setError(''); setMsg('');
    try {
      await uploadTemplateFiles(id, pendingFiles, setUploadProgress);
      setPendingFiles([]);
      setMsg(`✓ ${pendingFiles.length} file(s) uploaded and training started`);
      load();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Upload failed');
    } finally { setUploading(false); setUploadProgress(0); }
  };

  const handleRetrain = async () => {
    setRetraining(true); setMsg('');
    try {
      await retrainTemplate(id);
      setMsg('✓ Retraining queued for all files');
      load();
    } catch (e: any) { setError(e.response?.data?.detail || 'Retrain failed'); }
    finally { setRetraining(false); }
  };

  const handleDeleteFile = async (templateId: number, fileId: number) => {
    if (!confirm('Remove this file from the template?')) return;
    await deleteTemplateFile(templateId, fileId);
    load();
  };

  if (loading) return <div style={{ padding:40, color:'#6b7280', textAlign:'center' }}>Loading...</div>;
  if (!template) return <div style={{ padding:40, color:'#ef4444' }}>Template not found</div>;

  const doneCount = template.files.filter(f => f.processing_status === 'done').length;
  const processingCount = template.files.filter(f => f.processing_status === 'processing' || f.processing_status === 'pending').length;

  return (
    <div style={{ padding:28 }}>
      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:6 }}>
        <button onClick={() => router.push('/templates')}
          style={{ background:'none', border:'none', color:'#6b7280', cursor:'pointer', fontSize:13 }}>
          ← Templates
        </button>
      </div>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:20 }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:4 }}>
            <h1 style={{ fontSize:22, fontWeight:700, color:'#f1f5f9' }}>{template.name}</h1>
            <span className={`badge badge-${template.status}`}>{template.status}</span>
          </div>
          {template.description && <div style={{ fontSize:13, color:'#6b7280' }}>{template.description}</div>}
          <div style={{ fontSize:12, color:'#94a3b8', marginTop:4 }}>
            {template.file_count} files · {doneCount} trained · {processingCount} processing
          </div>
        </div>
        <div style={{ display:'flex', gap:10 }}>
          {template.file_count > 0 && (
            <button className="btn-secondary" onClick={handleRetrain} disabled={retraining}>
              {retraining ? '⟳ Retraining...' : '↻ Retrain All'}
            </button>
          )}
        </div>
      </div>

      {msg && <div style={{ background:'rgba(16,185,129,.1)', border:'1px solid rgba(16,185,129,.3)', color:'#10b981', padding:'10px 14px', borderRadius:8, fontSize:13, marginBottom:14 }}>{msg}</div>}
      {error && <div style={{ background:'rgba(239,68,68,.1)', border:'1px solid rgba(239,68,68,.3)', color:'#ef4444', padding:'10px 14px', borderRadius:8, fontSize:13, marginBottom:14 }}>{error}</div>}

      {/* Upload Zone */}
      <div className="card" style={{ padding:20, marginBottom:20 }}>
        <h3 style={{ fontSize:13, fontWeight:600, color:'#e2e8f0', marginBottom:12 }}>Upload Approved Content Files</h3>
        <div {...getRootProps()} style={{
          border: `2px dashed ${isDragActive ? '#6366f1' : '#374151'}`,
          borderRadius:10, padding:'28px 20px', textAlign:'center', cursor:'pointer',
          background: isDragActive ? 'rgba(99,102,241,.06)' : 'rgba(255,255,255,.02)',
          transition: 'all 0.2s', marginBottom:12
        }}>
          <input {...getInputProps()} />
          <div style={{ fontSize:28, marginBottom:8 }}>📁</div>
          <div style={{ fontSize:13, color:'#e2e8f0', marginBottom:4 }}>
            {isDragActive ? 'Drop files here' : 'Drag & drop images or videos'}
          </div>
          <div style={{ fontSize:12, color:'#6b7280' }}>
            JPG, PNG, GIF, WebP, MP4, MOV · Max 100MB per file
          </div>
        </div>

        {pendingFiles.length > 0 && (
          <div style={{ marginBottom:12 }}>
            <div style={{ fontSize:12, color:'#94a3b8', marginBottom:6 }}>
              {pendingFiles.length} file(s) selected:
            </div>
            <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
              {pendingFiles.map((f, i) => (
                <div key={i} style={{
                  background:'#1f2937', borderRadius:6, padding:'4px 10px',
                  fontSize:11, color:'#d1d5db', display:'flex', alignItems:'center', gap:6
                }}>
                  {f.name}
                  <span onClick={() => setPendingFiles(p => p.filter((_,j) => j !== i))}
                    style={{ cursor:'pointer', color:'#6b7280' }}>×</span>
                </div>
              ))}
            </div>
            {uploading && (
              <div style={{ marginTop:10 }}>
                <div style={{ height:4, background:'#1f2937', borderRadius:2, overflow:'hidden' }}>
                  <div style={{ height:'100%', width:`${uploadProgress}%`, background:'#6366f1', transition:'width 0.3s' }} />
                </div>
                <div style={{ fontSize:11, color:'#6b7280', marginTop:4 }}>{uploadProgress}% uploaded</div>
              </div>
            )}
            <button className="btn-primary" onClick={handleUpload} disabled={uploading} style={{ marginTop:10 }}>
              {uploading ? `Uploading... ${uploadProgress}%` : `Upload ${pendingFiles.length} File(s) & Train`}
            </button>
          </div>
        )}
      </div>

      {/* Files table */}
      {template.files.length > 0 && (
        <div className="card" style={{ padding:20 }}>
          <h3 style={{ fontSize:13, fontWeight:600, color:'#e2e8f0', marginBottom:14 }}>
            Template Files ({template.files.length})
          </h3>
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th style={{ width:40 }}></th>
                <th>File Name</th>
                <th>Size</th>
                <th>Status</th>
                <th>LLM Summary</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr></thead>
              <tbody>
                {template.files.map(tf => (
                  <FileRow key={tf.id} tf={tf} onDelete={() => handleDeleteFile(id, tf.id)} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
