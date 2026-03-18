'use client';
import { useEffect, useState } from 'react';
import { getReports, getReportDetail, exportReports, getTemplates, type Report, type Template } from '@/lib/api';
import { format } from 'date-fns';

const VERDICT_LABEL: Record<string, string> = {
  appropriate:'Appropriate', escalate:'Escalate', need_review:'Need to Review'
};
const ACTION_LABEL: Record<string, string> = {
  appropriate:'Appropriate ✓', escalate:'Escalate 🚨', need_review:'Need to Review ⚠️'
};

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [selected, setSelected] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Filters
  const [filterTemplate, setFilterTemplate] = useState('');
  const [filterVerdict, setFilterVerdict] = useState('');
  const [filterFrom, setFilterFrom] = useState('');
  const [filterTo, setFilterTo] = useState('');

  const load = () => {
    setLoading(true);
    const params: any = {};
    if (filterTemplate) params.template_id = filterTemplate;
    if (filterVerdict)  params.verdict = filterVerdict;
    if (filterFrom)     params.from_date = filterFrom;
    if (filterTo)       params.to_date = filterTo;
    getReports(params).then(setReports).finally(() => setLoading(false));
  };

  useEffect(() => { getTemplates().then(setTemplates); }, []);
  useEffect(() => { load(); }, [filterTemplate, filterVerdict, filterFrom, filterTo]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const params: any = {};
      if (filterTemplate) params.template_id = filterTemplate;
      if (filterFrom)     params.from_date = filterFrom;
      if (filterTo)       params.to_date = filterTo;
      const blob = await exportReports(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `validation_report_${format(new Date(), 'yyyyMMdd_HHmmss')}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { alert('Export failed. Check API is running.'); }
    finally { setExporting(false); }
  };

  const openDetail = async (report: Report) => {
    setDetailLoading(true);
    setSelected(null);
    try {
      const detail = await getReportDetail(report.id);
      setSelected(detail);
    } catch (e) { alert('Could not load detail'); }
    finally { setDetailLoading(false); }
  };

  return (
    <div style={{ padding:28 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
        <div>
          <h1 style={{ fontSize:22, fontWeight:700, color:'#f1f5f9' }}>Reports</h1>
          <p style={{ fontSize:13, color:'#6b7280', marginTop:3 }}>
            All validation records · {reports.length} results
          </p>
        </div>
        <button className="btn-primary" onClick={handleExport} disabled={exporting}>
          {exporting ? '⟳ Exporting...' : '⬇ Export to Excel'}
        </button>
      </div>

      {/* Filters */}
      <div className="card" style={{ padding:14, marginBottom:16, display:'flex', gap:12, flexWrap:'wrap', alignItems:'flex-end' }}>
        <div>
          <label className="label">Template</label>
          <select className="input" style={{ width:200 }} value={filterTemplate} onChange={e => setFilterTemplate(e.target.value)}>
            <option value="">All Templates</option>
            {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Verdict</label>
          <select className="input" style={{ width:160 }} value={filterVerdict} onChange={e => setFilterVerdict(e.target.value)}>
            <option value="">All Verdicts</option>
            <option value="appropriate">Appropriate</option>
            <option value="escalate">Escalate</option>
            <option value="need_review">Need to Review</option>
          </select>
        </div>
        <div>
          <label className="label">From Date</label>
          <input type="date" className="input" style={{ width:160 }} value={filterFrom} onChange={e => setFilterFrom(e.target.value)} />
        </div>
        <div>
          <label className="label">To Date</label>
          <input type="date" className="input" style={{ width:160 }} value={filterTo} onChange={e => setFilterTo(e.target.value)} />
        </div>
        <button className="btn-secondary" onClick={() => { setFilterTemplate(''); setFilterVerdict(''); setFilterFrom(''); setFilterTo(''); }}>
          Clear
        </button>
      </div>

      {/* Table */}
      <div className="card" style={{ padding:20, marginBottom: selected ? 16 : 0 }}>
        {loading ? (
          <div style={{ textAlign:'center', padding:40, color:'#6b7280' }}>Loading reports...</div>
        ) : reports.length === 0 ? (
          <div style={{ textAlign:'center', padding:40, color:'#6b7280', fontSize:13 }}>
            No reports found. <a href="/validate" style={{ color:'#6366f1' }}>Run a validation →</a>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th>Report Ref</th>
                <th>Post Timestamp</th>
                <th>Post Description</th>
                <th>Template</th>
                <th>Suspected Match</th>
                <th>Exact Pixel?</th>
                <th>MCC Compliant?</th>
                <th>Action</th>
                <th>Validated At</th>
                <th></th>
              </tr></thead>
              <tbody>
                {reports.map(r => (
                  <tr key={r.id}>
                    <td style={{ fontFamily:'monospace', fontSize:12, color:'#6366f1' }}>{r.report_ref}</td>
                    <td style={{ fontSize:12, color:'#94a3b8', whiteSpace:'nowrap' }}>
                      {/* post_timestamp comes from validation; show dash if not available */}—
                    </td>
                    <td style={{ maxWidth:200, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', color:'#94a3b8', fontSize:12 }}>
                      {r.input_source || '—'}
                    </td>
                    <td>
                      <span style={{ fontSize:12, fontWeight:500, color:'#e2e8f0' }}>{r.template_name}</span>
                    </td>
                    <td>
                      {r.suspected_matches > 0
                        ? <span style={{ color:'#10b981', fontSize:12 }}>✓ {r.suspected_matches} match{r.suspected_matches > 1 ? 'es' : ''}</span>
                        : <span style={{ color:'#4b5563', fontSize:12 }}>No match</span>}
                    </td>
                    <td>
                      {r.exact_matches > 0
                        ? <span className="badge badge-appropriate">Yes</span>
                        : <span className="badge badge-pending">No</span>}
                    </td>
                    <td>
                      {r.mcc_compliant === true && <span className="badge badge-appropriate">Yes</span>}
                      {r.mcc_compliant === false && <span className="badge badge-escalate">No</span>}
                      {r.mcc_compliant === null && <span style={{ color:'#4b5563', fontSize:12 }}>—</span>}
                    </td>
                    <td>
                      <span className={`badge badge-${r.overall_verdict || 'pending'}`}>
                        {ACTION_LABEL[r.overall_verdict || ''] || r.overall_verdict || '—'}
                      </span>
                    </td>
                    <td style={{ fontSize:12, color:'#6b7280', whiteSpace:'nowrap' }}>
                      {format(new Date(r.created_at), 'MM/dd/yy HH:mm')}
                    </td>
                    <td>
                      <button onClick={() => openDetail(r)}
                        style={{ background:'transparent', border:'1px solid #374151', color:'#94a3b8',
                          padding:'4px 10px', borderRadius:5, fontSize:11, cursor:'pointer' }}>
                        Detail
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail drawer */}
      {(detailLoading || selected) && (
        <div className="card" style={{ padding:24 }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
            <h3 style={{ fontSize:14, fontWeight:600, color:'#e2e8f0' }}>
              {selected ? `Report ${selected.report.report_ref}` : 'Loading detail...'}
            </h3>
            <button onClick={() => setSelected(null)} style={{ background:'none', border:'none', color:'#6b7280', cursor:'pointer', fontSize:18 }}>×</button>
          </div>

          {detailLoading && <div style={{ textAlign:'center', padding:20, color:'#6b7280' }}>Loading...</div>}

          {selected && (
            <>
              {/* Summary row */}
              <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:12, marginBottom:20 }}>
                {[
                  { label:'Template', value: selected.report.template_name },
                  { label:'Files Compared', value: selected.report.total_files_compared },
                  { label:'Suspected Matches', value: selected.report.suspected_matches },
                  { label:'Exact Pixel Matches', value: selected.report.exact_matches },
                  { label:'MCC Compliant', value: selected.report.mcc_compliant === true ? 'Yes ✅' : selected.report.mcc_compliant === false ? 'No ❌' : '—' },
                ].map(s => (
                  <div key={s.label} style={{ background:'#0f1117', borderRadius:8, padding:'12px 14px' }}>
                    <div style={{ fontSize:11, color:'#6b7280', marginBottom:4 }}>{s.label}</div>
                    <div style={{ fontSize:15, fontWeight:600, color:'#e2e8f0' }}>{s.value}</div>
                  </div>
                ))}
              </div>

              {/* Post info */}
              {(selected.validation.post_description || selected.validation.post_timestamp) && (
                <div style={{ background:'#0f1117', borderRadius:8, padding:'12px 14px', marginBottom:16, fontSize:12 }}>
                  {selected.validation.post_timestamp && (
                    <div style={{ marginBottom:4 }}>
                      <span style={{ color:'#6b7280' }}>Post Timestamp: </span>
                      <span style={{ color:'#d1d5db' }}>{selected.validation.post_timestamp}</span>
                    </div>
                  )}
                  {selected.validation.post_platform && (
                    <div style={{ marginBottom:4 }}>
                      <span style={{ color:'#6b7280' }}>Platform: </span>
                      <span style={{ color:'#d1d5db' }}>{selected.validation.post_platform}</span>
                    </div>
                  )}
                  {selected.validation.post_description && (
                    <div>
                      <span style={{ color:'#6b7280' }}>Post Description: </span>
                      <span style={{ color:'#d1d5db' }}>{selected.validation.post_description}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Detailed match table */}
              <div className="table-wrap">
                <table>
                  <thead><tr>
                    <th>Template File</th>
                    <th>Trained Content Suspected Match</th>
                    <th>Exact Pixel Match?</th>
                    <th>MCC Compliant?</th>
                    <th>LLM Score</th>
                    <th>Pixel Score</th>
                    <th>Overall</th>
                    <th>Action</th>
                  </tr></thead>
                  <tbody>
                    {selected.matches.map((m: any, i: number) => (
                      <tr key={i} style={{ background: m.is_suspected_match ? 'rgba(99,102,241,.04)' : undefined }}>
                        <td style={{ fontSize:12 }}>{m.template_file_name}</td>
                        <td>
                          {m.is_suspected_match
                            ? <span style={{ color:'#10b981', fontSize:12 }}>✓ {selected.report.template_name} › {m.template_file_name}</span>
                            : <span style={{ color:'#4b5563', fontSize:12 }}>No Match</span>}
                        </td>
                        <td>
                          {m.is_exact_pixel_match
                            ? <span className="badge badge-appropriate">Yes</span>
                            : <span className="badge badge-pending">No</span>}
                        </td>
                        <td>
                          {selected.report.mcc_compliant === true
                            ? <span className="badge badge-appropriate">Yes</span>
                            : selected.report.mcc_compliant === false
                            ? <span className="badge badge-escalate">No</span>
                            : <span style={{ color:'#4b5563', fontSize:12 }}>—</span>}
                        </td>
                        <td style={{ fontSize:12 }}>{Number(m.llm_similarity_score).toFixed(1)}%</td>
                        <td style={{ fontSize:12 }}>{Number(m.pixel_similarity_score).toFixed(1)}%</td>
                        <td>
                          <span style={{
                            fontWeight:600, fontSize:13,
                            color: Number(m.overall_similarity_score) >= 85 ? '#10b981'
                              : Number(m.overall_similarity_score) >= 65 ? '#f59e0b' : '#6b7280'
                          }}>
                            {Number(m.overall_similarity_score).toFixed(1)}%
                          </span>
                        </td>
                        <td>
                          <span className={`badge badge-${selected.report.overall_verdict || 'pending'}`} style={{ fontSize:10 }}>
                            {ACTION_LABEL[selected.report.overall_verdict || ''] || '—'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
