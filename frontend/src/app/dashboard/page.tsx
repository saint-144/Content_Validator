'use client';
import { useEffect, useState } from 'react';
import { getDashboardStats, type DashboardStats } from '@/lib/api';
import { format } from 'date-fns';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

const VERDICT_COLORS: Record<string, string> = {
  appropriate: '#10b981', escalate: '#ef4444', need_review: '#f59e0b'
};
const PIE_COLORS = ['#10b981','#ef4444','#f59e0b','#6366f1','#3b82f6'];

function StatCard({ icon, label, value, sub, color = '#6366f1' }: any) {
  return (
    <div className="card" style={{ padding: 20 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div>
          <div style={{ fontSize:12, color:'#94a3b8', marginBottom:6 }}>{label}</div>
          <div style={{ fontSize:30, fontWeight:700, color:'#f1f5f9', lineHeight:1 }}>{value}</div>
          {sub && <div style={{ fontSize:11, color:'#6b7280', marginTop:5 }}>{sub}</div>}
        </div>
        <div style={{
          width:40, height:40, borderRadius:10,
          background: color+'22', display:'flex',
          alignItems:'center', justifyContent:'center', fontSize:18
        }}>{icon}</div>
      </div>
    </div>
  );
}

function verdictLabel(v: string) {
  return { appropriate:'Appropriate', escalate:'Escalate', need_review:'Need Review' }[v] || v;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch(() => setError('Could not load dashboard. Is the API running on port 8000?'))
      .finally(() => setLoading(false));
    const interval = setInterval(() => getDashboardStats().then(setStats).catch(() => {}), 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return (
    <div style={{ padding:40, textAlign:'center', color:'#6b7280' }}>
      <div className="spin" style={{ fontSize:24 }}>⟳</div>
      <div style={{ marginTop:12, fontSize:14 }}>Loading dashboard...</div>
    </div>
  );

  if (error) return (
    <div style={{ padding:40, textAlign:'center' }}>
      <div style={{ color:'#ef4444', fontSize:14 }}>{error}</div>
      <a href="http://localhost:8000/docs" target="_blank"
         style={{ color:'#6366f1', fontSize:13, marginTop:8, display:'block' }}>
        Check API status →
      </a>
    </div>
  );

  if (!stats) return null;

  // Prepare chart data
  const verdictPieData = [
    { name:'Appropriate', value: stats.appropriate_count, color:'#10b981' },
    { name:'Escalate',    value: stats.escalate_count,    color:'#ef4444' },
    { name:'Need Review', value: stats.need_review_count, color:'#f59e0b' },
  ].filter(d => d.value > 0);

  // Group verdicts by day for line chart
  const dayMap: Record<string, any> = {};
  stats.verdicts_by_day.forEach(({ day, verdict, count }) => {
    if (!dayMap[day]) dayMap[day] = { day };
    dayMap[day][verdict] = count;
  });
  const trendData = Object.values(dayMap).slice(-14);

  const mccPie = [
    { name:'MCC Compliant',   value: stats.mcc_compliant_count,     color:'#10b981' },
    { name:'Non-Compliant',   value: stats.mcc_non_compliant_count, color:'#ef4444' },
  ].filter(d => d.value > 0);

  return (
    <div style={{ padding:28 }}>
      {/* Header */}
      <div style={{ marginBottom:24 }}>
        <h1 style={{ fontSize:22, fontWeight:700, color:'#f1f5f9' }}>Dashboard</h1>
        <p style={{ fontSize:13, color:'#6b7280', marginTop:3 }}>
          Real-time overview · Last updated {format(new Date(), 'HH:mm:ss')}
        </p>
      </div>

      {/* Stat cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(180px,1fr))', gap:14, marginBottom:24 }}>
        <StatCard icon="⊞" label="Templates"       value={stats.total_templates}       color="#6366f1" />
        <StatCard icon="📁" label="Trained Files"   value={stats.total_trained_files}   color="#8b5cf6" />
        <StatCard icon="⦿" label="Total Validations" value={stats.total_validations}   color="#3b82f6" />
        <StatCard icon="📅" label="Today"           value={stats.validations_today}     sub="validations today" color="#06b6d4" />
        <StatCard icon="✅" label="Appropriate"      value={stats.appropriate_count}    color="#10b981" />
        <StatCard icon="🚨" label="Escalate"         value={stats.escalate_count}       color="#ef4444" />
        <StatCard icon="⚠️" label="Need Review"     value={stats.need_review_count}     color="#f59e0b" />
        <StatCard icon="🛡️" label="MCC Compliant"  value={stats.mcc_compliant_count}    color="#10b981" />
      </div>

      {/* Charts row 1 */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginBottom:16 }}>
        {/* Trend line chart */}
        <div className="card" style={{ padding:20 }}>
          <h3 style={{ fontSize:13, fontWeight:600, color:'#e2e8f0', marginBottom:16 }}>
            Validation Trend (Last 14 Days)
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trendData} margin={{ top:5, right:5, bottom:5, left:-20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="day" tick={{ fontSize:10, fill:'#6b7280' }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize:10, fill:'#6b7280' }} />
              <Tooltip contentStyle={{ background:'#161b27', border:'1px solid #374151', fontSize:12 }} />
              <Legend wrapperStyle={{ fontSize:11 }} />
              <Line type="monotone" dataKey="appropriate" stroke="#10b981" dot={false} name="Appropriate" />
              <Line type="monotone" dataKey="escalate"    stroke="#ef4444" dot={false} name="Escalate" />
              <Line type="monotone" dataKey="need_review" stroke="#f59e0b" dot={false} name="Need Review" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Verdict pie */}
        <div className="card" style={{ padding:20 }}>
          <h3 style={{ fontSize:13, fontWeight:600, color:'#e2e8f0', marginBottom:16 }}>Verdict Distribution</h3>
          {verdictPieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={verdictPieData} cx="50%" cy="50%" outerRadius={75}
                     dataKey="value" nameKey="name" label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}
                     labelLine={false} fontSize={11}>
                  {verdictPieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip contentStyle={{ background:'#161b27', border:'1px solid #374151', fontSize:12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <div style={{ height:200, display:'flex', alignItems:'center', justifyContent:'center', color:'#6b7280', fontSize:13 }}>No data yet</div>}
        </div>
      </div>

      {/* Charts row 2 */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:16, marginBottom:16 }}>
        {/* Top templates bar */}
        <div className="card" style={{ padding:20, gridColumn:'span 2' }}>
          <h3 style={{ fontSize:13, fontWeight:600, color:'#e2e8f0', marginBottom:16 }}>Most Validated Templates</h3>
          {stats.top_templates.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={stats.top_templates} margin={{ top:5, right:5, bottom:5, left:-20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="name" tick={{ fontSize:10, fill:'#6b7280' }} />
                <YAxis tick={{ fontSize:10, fill:'#6b7280' }} />
                <Tooltip contentStyle={{ background:'#161b27', border:'1px solid #374151', fontSize:12 }} />
                <Bar dataKey="count" fill="#6366f1" radius={[4,4,0,0]} name="Validations" />
              </BarChart>
            </ResponsiveContainer>
          ) : <div style={{ height:160, display:'flex', alignItems:'center', justifyContent:'center', color:'#6b7280', fontSize:13 }}>No data yet</div>}
        </div>

        {/* MCC compliance pie */}
        <div className="card" style={{ padding:20 }}>
          <h3 style={{ fontSize:13, fontWeight:600, color:'#e2e8f0', marginBottom:16 }}>MCC Compliance</h3>
          {mccPie.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <PieChart>
                <Pie data={mccPie} cx="50%" cy="50%" outerRadius={60}
                     dataKey="value" label={({ name, percent }) => `${(percent*100).toFixed(0)}%`} fontSize={11}>
                  {mccPie.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip contentStyle={{ background:'#161b27', border:'1px solid #374151', fontSize:12 }} />
                <Legend wrapperStyle={{ fontSize:10 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <div style={{ height:160, display:'flex', alignItems:'center', justifyContent:'center', color:'#6b7280', fontSize:12 }}>No data yet</div>}
        </div>
      </div>

      {/* Recent validations table */}
      <div className="card" style={{ padding:20 }}>
        <h3 style={{ fontSize:13, fontWeight:600, color:'#e2e8f0', marginBottom:14 }}>Recent Validations</h3>
        {stats.recent_validations.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead><tr>
                <th>ID</th><th>Template</th><th>Source</th>
                <th>Verdict</th><th>MCC</th><th>Time</th>
              </tr></thead>
              <tbody>
                {stats.recent_validations.map((v: any) => (
                  <tr key={v.id}>
                    <td style={{ color:'#6b7280' }}>#{v.id}</td>
                    <td>{v.template_name}</td>
                    <td style={{ maxWidth:200, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {v.input_file_name}
                    </td>
                    <td>
                      <span className={`badge badge-${v.verdict}`}>{verdictLabel(v.verdict || '')}</span>
                    </td>
                    <td>
                      {v.mcc_compliant === true && <span className="badge badge-appropriate">Yes</span>}
                      {v.mcc_compliant === false && <span className="badge badge-escalate">No</span>}
                      {v.mcc_compliant === null && <span className="badge badge-pending">—</span>}
                    </td>
                    <td style={{ color:'#6b7280', fontSize:12 }}>
                      {format(new Date(v.created_at), 'MM/dd HH:mm')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ textAlign:'center', padding:'30px 0', color:'#6b7280', fontSize:13 }}>
            No validations yet. <a href="/validate" style={{ color:'#6366f1' }}>Run your first validation →</a>
          </div>
        )}
      </div>
    </div>
  );
}
