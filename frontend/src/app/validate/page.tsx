'use client';
import { useEffect, useState, useCallback, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { getTemplates, validateUpload, validateUrl, getValidationStatus, getValidation, type Template, type Validation, type ValidationMatch } from '@/lib/api';
import { format } from 'date-fns';

type InputMode = 'upload' | 'url';

const VERDICT_CONFIG: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  appropriate: { label:'Appropriate',   color:'#10b981', bg:'rgba(16,185,129,.12)', icon:'✅' },
  escalate:    { label:'Escalate',      color:'#ef4444', bg:'rgba(239,68,68,.12)',  icon:'🚨' },
  need_review: { label:'Need to Review',color:'#f59e0b', bg:'rgba(245,158,11,.12)', icon:'⚠️' },
};

function ScoreBar({ score }: { score: number }) {
  const color = score >= 85 ? '#10b981' : score >= 65 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
      <div style={{ flex:1, height:6, background:'#1f2937', borderRadius:3, overflow:'hidden' }}>
        <div style={{ width:`${score}%`, height:'100%', background:color, borderRadius:3, transition:'width 0.6s' }} />
      </div>
      <span style={{ fontSize:11, color, fontWeight:600, minWidth:36 }}>{score.toFixed(0)}%</span>
    </div>
  );
}

function MatchRow({ match, templateName, rank }: { match: ValidationMatch; templateName: string; rank: number }) {
  const [exp, setExp] = useState(false);
  return (
    <>
      <tr style={{ background: match.is_suspected_match ? 'rgba(245,158,11,.04)' : undefined }}>
        <td style={{ color:'#6b7280', fontWeight:600 }}>#{rank}</td>
        <td>
          <div style={{ fontWeight:500, color:'#e2e8f0', fontSize:13 }}>{match.template_file_name}</div>
          <div style={{ fontSize:11, color:'#6b7280', marginTop:2 }}>{templateName}</div>
        </td>
        <td>
          {match.is_suspected_match
            ? <span style={{ color:'#10b981', fontSize:12, fontWeight:600 }}>✓ {templateName} › {match.template_file_name}</span>
            : <span style={{ color:'#4b5563', fontSize:12 }}>No Match</span>}
        </td>
        <td>
          {match.is_exact_pixel_match
            ? <span className="badge badge-appropriate">Yes</span>
            : <span className="badge badge-pending">No</span>}
        </td>
        <td><ScoreBar score={Number(match.overall_similarity_score)} /></td>
        <td>
          {match.is_suspected_match
            ? <span className="badge badge-appropriate">Match</span>
            : <span className="badge badge-pending">No Match</span>}
        </td>
        <td>
          {match.match_reasoning && (
            <button onClick={() => setExp(!exp)}
              style={{ background:'transparent', border:'1px solid #374151', color:'#94a3b8',
                padding:'3px 8px', borderRadius:5, fontSize:11, cursor:'pointer' }}>
              {exp ? 'Less' : 'Reason'}
            </button>
          )}
        </td>
      </tr>
      {exp && match.match_reasoning && (
        <tr>
          <td colSpan={7} style={{ background:'#0f1117', padding:'10px 16px' }}>
            <div style={{ fontSize:12, color:'#94a3b8', lineHeight:1.7 }}>
              <span style={{ color:'#6b7280' }}>Reasoning: </span>{match.match_reasoning}
              {match.visual_differences && (
                <><br /><span style={{ color:'#6b7280' }}>Differences: </span>{match.visual_differences}</>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function ValidatePage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [mode, setMode] = useState<InputMode>('upload');
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [postDesc, setPostDesc] = useState('');
  const [postTs, setPostTs] = useState('');
  const [postPlatform, setPostPlatform] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [validationId, setValidationId] = useState<number | null>(null);
  const [pollingStatus, setPollingStatus] = useState('');
  const [result, setResult] = useState<Validation | null>(null);
  const [error, setError] = useState('');
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    getTemplates().then(ts => {
      setTemplates(ts.filter(t => t.status === 'ready'));
    });
  }, []);

  const onDrop = useCallback((files: File[]) => {
    if (files[0]) { setFile(files[0]); setError(''); }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { 'image/*': [], 'video/*': [] }, maxFiles: 1, maxSize: 100 * 1024 * 1024
  });

  const startPolling = (vid: number) => {
    setValidationId(vid);
    setPollingStatus('processing');
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        const status = await getValidationStatus(vid);
        setPollingStatus(status.status);
        if (status.status === 'completed' || status.status === 'error') {
          clearInterval(pollingRef.current!);
          if (status.status === 'completed') {
            const full = await getValidation(vid);
            setResult(full);
          } else {
            setError(status.error || 'Validation failed');
          }
          setSubmitting(false);
        }
      } catch (e) {
        clearInterval(pollingRef.current!);
        setError('Polling failed');
        setSubmitting(false);
      }
    }, 2000);
  };

  const handleSubmit = async () => {
    if (!selectedTemplate) { setError('Please select a template'); return; }
    setSubmitting(true); setError(''); setResult(null); setProgress(0);

    try {
      if (mode === 'upload') {
        if (!file) { setError('Please select a file'); setSubmitting(false); return; }
        const fd = new FormData();
        fd.append('file', file);
        fd.append('template_id', String(selectedTemplate));
        if (postTs) fd.append('post_timestamp', postTs);
        if (postDesc) fd.append('post_description', postDesc);
        if (postPlatform) fd.append('post_platform', postPlatform);
        const res = await validateUpload(fd, setProgress);
        startPolling(res.validation_id);
      } else {
        if (!url.trim()) { setError('Please enter a URL'); setSubmitting(false); return; }
        const res = await validateUrl({
          url: url.trim(), template_id: selectedTemplate,
          post_timestamp: postTs || undefined,
          post_description: postDesc || undefined,
          post_platform: postPlatform || undefined
        });
        startPolling(res.validation_id);
      }
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Submission failed');
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setFile(null); setUrl(''); setResult(null); setValidationId(null);
    setPollingStatus(''); setError(''); setProgress(0);
  };

  const verdictCfg = result?.overall_verdict ? VERDICT_CONFIG[result.overall_verdict] : null;
  const readyTemplates = templates.filter(t => t.status === 'ready');

  return (
    <div style={{ padding:28 }}>
      <div style={{ marginBottom:24 }}>
        <h1 style={{ fontSize:22, fontWeight:700, color:'#f1f5f9' }}>Validate Content</h1>
        <p style={{ fontSize:13, color:'#6b7280', marginTop:3 }}>
          Upload a file or paste a public URL and select a template to validate against
        </p>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'360px 1fr', gap:20, alignItems:'start' }}>
        {/* Left: Form */}
        <div>
          <div className="card" style={{ padding:20 }}>
            {/* Template selector */}
            <div style={{ marginBottom:18 }}>
              <label className="label">Select Template *</label>
              {readyTemplates.length === 0 ? (
                <div style={{ fontSize:12, color:'#f59e0b', padding:'10px', background:'rgba(245,158,11,.08)', borderRadius:7 }}>
                  No ready templates. <a href="/templates" style={{ color:'#6366f1' }}>Create and train one first →</a>
                </div>
              ) : (
                <select className="input" value={selectedTemplate || ''} onChange={e => setSelectedTemplate(Number(e.target.value))}>
                  <option value="">Choose template...</option>
                  {readyTemplates.map(t => (
                    <option key={t.id} value={t.id}>{t.name} ({t.file_count} files)</option>
                  ))}
                </select>
              )}
            </div>

            {/* Input mode toggle */}
            <div style={{ marginBottom:16 }}>
              <label className="label">Input Type</label>
              <div style={{ display:'flex', gap:6 }}>
                {(['upload','url'] as InputMode[]).map(m => (
                  <button key={m} onClick={() => setMode(m)} style={{
                    flex:1, padding:'8px 12px', borderRadius:7, border:'1px solid',
                    borderColor: mode === m ? '#6366f1' : '#374151',
                    background: mode === m ? 'rgba(99,102,241,.12)' : 'transparent',
                    color: mode === m ? '#6366f1' : '#94a3b8',
                    cursor:'pointer', fontSize:13, fontWeight:500
                  }}>
                    {m === 'upload' ? '📁 Upload File' : '🔗 Public URL'}
                  </button>
                ))}
              </div>
            </div>

            {/* Input area */}
            {mode === 'upload' ? (
              <div style={{ marginBottom:16 }}>
                {!file ? (
                  <div {...getRootProps()} style={{
                    border:`2px dashed ${isDragActive ? '#6366f1' : '#374151'}`,
                    borderRadius:10, padding:'24px 16px', textAlign:'center', cursor:'pointer',
                    background: isDragActive ? 'rgba(99,102,241,.06)' : 'transparent'
                  }}>
                    <input {...getInputProps()} />
                    <div style={{ fontSize:28, marginBottom:6 }}>⬆️</div>
                    <div style={{ fontSize:12, color:'#e2e8f0' }}>Drop image or video here</div>
                    <div style={{ fontSize:11, color:'#6b7280', marginTop:4 }}>or click to browse</div>
                  </div>
                ) : (
                  <div style={{ background:'#1a2233', border:'1px solid #374151', borderRadius:8, padding:'10px 14px', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                    <div>
                      <div style={{ fontSize:13, color:'#e2e8f0' }}>{file.name}</div>
                      <div style={{ fontSize:11, color:'#6b7280' }}>{(file.size/1024).toFixed(0)} KB</div>
                    </div>
                    <button onClick={() => setFile(null)} style={{ background:'none', border:'none', color:'#6b7280', cursor:'pointer', fontSize:16 }}>×</button>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ marginBottom:16 }}>
                <label className="label">Public Image/Post URL</label>
                <input className="input" value={url} onChange={e => setUrl(e.target.value)}
                  placeholder="https://example.com/image.jpg" />
              </div>
            )}

            {/* Metadata */}
            <div style={{ borderTop:'1px solid #1f2937', paddingTop:14, marginBottom:16 }}>
              <div style={{ fontSize:11, color:'#6b7280', marginBottom:10, textTransform:'uppercase', letterSpacing:'0.5px' }}>
                Post Metadata (Optional)
              </div>
              <div style={{ marginBottom:10 }}>
                <label className="label">Post Timestamp</label>
                <input type="datetime-local" className="input" value={postTs} onChange={e => setPostTs(e.target.value)} />
              </div>
              <div style={{ marginBottom:10 }}>
                <label className="label">Platform</label>
                <select className="input" value={postPlatform} onChange={e => setPostPlatform(e.target.value)}>
                  <option value="">Select platform...</option>
                  {['Instagram','Facebook','Twitter/X','LinkedIn','YouTube','TikTok','Other'].map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Post Description / Caption</label>
                <textarea className="input" value={postDesc} onChange={e => setPostDesc(e.target.value)}
                  rows={3} placeholder="Paste the post caption here..." />
              </div>
            </div>

            {error && <div style={{ color:'#ef4444', fontSize:12, marginBottom:10, padding:'8px 12px', background:'rgba(239,68,68,.08)', borderRadius:7 }}>{error}</div>}

            {submitting ? (
              <div style={{ textAlign:'center', padding:'16px 0' }}>
                {progress > 0 && progress < 100 ? (
                  <>
                    <div style={{ height:4, background:'#1f2937', borderRadius:2, overflow:'hidden', marginBottom:8 }}>
                      <div style={{ height:'100%', width:`${progress}%`, background:'#6366f1', transition:'width 0.3s' }} />
                    </div>
                    <div style={{ fontSize:12, color:'#6b7280' }}>Uploading {progress}%...</div>
                  </>
                ) : (
                  <div style={{ fontSize:13, color:'#6366f1' }}>
                    <span className="spin">⟳</span>
                    {' '}Running LLM analysis... this may take 30-60 seconds
                  </div>
                )}
              </div>
            ) : result ? (
              <button className="btn-secondary" onClick={resetForm} style={{ width:'100%', justifyContent:'center' }}>
                ↩ Validate Another
              </button>
            ) : (
              <button className="btn-primary" onClick={handleSubmit}
                disabled={!selectedTemplate || (mode === 'upload' ? !file : !url.trim())}
                style={{ width:'100%', justifyContent:'center' }}>
                ⦿ Run Validation
              </button>
            )}
          </div>
        </div>

        {/* Right: Results */}
        <div>
          {!result && !submitting && (
            <div className="card" style={{ padding:40, textAlign:'center' }}>
              <div style={{ fontSize:48, marginBottom:12, opacity:0.3 }}>⦿</div>
              <div style={{ fontSize:14, color:'#4b5563' }}>
                Select a template and provide content to validate
              </div>
            </div>
          )}

          {submitting && (
            <div className="card" style={{ padding:40, textAlign:'center' }}>
              <div style={{ fontSize:40, marginBottom:12 }}>
                <span className="spin">⟳</span>
              </div>
              <div style={{ fontSize:14, color:'#94a3b8', marginBottom:6 }}>
                {pollingStatus === 'processing' ? 'LLM is analyzing your content...' : 'Queuing validation...'}
              </div>
              <div style={{ fontSize:12, color:'#6b7280' }}>
                Comparing against all trained files · Typically 30–90 seconds
              </div>
            </div>
          )}

          {result && verdictCfg && (
            <div>
              {/* Verdict banner */}
              <div style={{
                background: verdictCfg.bg, border:`1px solid ${verdictCfg.color}44`,
                borderRadius:12, padding:20, marginBottom:16, display:'flex',
                justifyContent:'space-between', alignItems:'center'
              }}>
                <div>
                  <div style={{ fontSize:11, color:'#94a3b8', marginBottom:4, textTransform:'uppercase', letterSpacing:'0.5px' }}>
                    Validation Result
                  </div>
                  <div style={{ fontSize:22, fontWeight:700, color:verdictCfg.color }}>
                    {verdictCfg.icon} {verdictCfg.label}
                  </div>
                  {result.post_description && (
                    <div style={{ fontSize:12, color:'#9ca3af', marginTop:6, maxWidth:500 }}>
                      {result.post_description.slice(0, 200)}{result.post_description.length > 200 ? '...' : ''}
                    </div>
                  )}
                </div>
                <div style={{ textAlign:'right' }}>
                  <div style={{ fontSize:11, color:'#6b7280', marginBottom:4 }}>MCC Compliant</div>
                  <div style={{ fontSize:18, fontWeight:700 }}>
                    {result.mcc_compliant === true ? <span style={{ color:'#10b981' }}>✅ Yes</span>
                      : result.mcc_compliant === false ? <span style={{ color:'#ef4444' }}>❌ No</span>
                      : <span style={{ color:'#6b7280' }}>—</span>}
                  </div>
                  <div style={{ fontSize:11, color:'#6b7280', marginTop:6 }}>
                    {result.processing_time_ms ? `${(result.processing_time_ms/1000).toFixed(1)}s` : ''}
                  </div>
                </div>
              </div>

              {/* Post metadata row */}
              <div className="card" style={{ padding:14, marginBottom:16, display:'flex', gap:24, fontSize:12 }}>
                <div>
                  <span style={{ color:'#6b7280' }}>Template: </span>
                  <span style={{ color:'#e2e8f0', fontWeight:500 }}>{result.template_name}</span>
                </div>
                {result.post_timestamp && (
                  <div>
                    <span style={{ color:'#6b7280' }}>Post Time: </span>
                    <span style={{ color:'#e2e8f0' }}>{format(new Date(result.post_timestamp), 'PPpp')}</span>
                  </div>
                )}
                {result.post_platform && (
                  <div>
                    <span style={{ color:'#6b7280' }}>Platform: </span>
                    <span style={{ color:'#e2e8f0' }}>{result.post_platform}</span>
                  </div>
                )}
                <div>
                  <span style={{ color:'#6b7280' }}>Files Compared: </span>
                  <span style={{ color:'#e2e8f0' }}>{result.matches.length}</span>
                </div>
              </div>

              {/* Results table */}
              <div className="card" style={{ padding:20 }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}>
                  <h3 style={{ fontSize:13, fontWeight:600, color:'#e2e8f0' }}>
                    Per-File Comparison Results
                  </h3>
                  <div style={{ fontSize:12, color:'#6b7280' }}>
                    {result.matches.filter(m => m.is_suspected_match).length} suspected matches ·{' '}
                    {result.matches.filter(m => m.is_exact_pixel_match).length} exact pixel matches
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead><tr>
                      <th>#</th>
                      <th>Template File</th>
                      <th>Trained Content Suspected Match</th>
                      <th>Exact Pixel Match?</th>
                      <th>Similarity Score</th>
                      <th>Flag</th>
                      <th></th>
                    </tr></thead>
                    <tbody>
                      {[...result.matches]
                        .sort((a, b) => Number(b.overall_similarity_score) - Number(a.overall_similarity_score))
                        .map((m, i) => (
                          <MatchRow key={m.id} match={m} templateName={result.template_name} rank={i+1} />
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
