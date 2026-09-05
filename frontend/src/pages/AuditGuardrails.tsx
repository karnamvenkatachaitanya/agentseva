import { useCallback, useEffect, useState } from 'react';
import { 
  ShieldCheck, 
  AlertOctagon, 
  RotateCcw, 
  Activity, 
  Layers, 
  Clock, 
  TrendingUp, 
  ShieldAlert,
  Zap
} from 'lucide-react';
import { api, type AuditTrace } from '../api';
import { badge, inr } from '../ui';

export function AuditGuardrails() {
  const [traces, setTraces] = useState<AuditTrace[]>([]);
  const [limits, setLimits] = useState<Record<string, number>>({});
  const [metrics, setMetrics] = useState<Record<string, number>>({});
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setError('');
      const [t, l, m] = await Promise.all([api.recentTraces(60), api.limits(), api.metrics()]);
      setTraces(t);
      setLimits(l);
      setMetrics(m);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div style={{ padding: '24px 32px', height: '100%', overflowY: 'auto', background: '#f8fafc', color: '#0f172a' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontFamily: 'Plus Jakarta Sans, sans-serif', fontSize: 20, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8, color: '#0c2340' }}>
            <ShieldCheck size={22} style={{ color: '#2563eb' }} />
            Financial Guardrails & Telemetry
          </h1>
          <p style={{ color: '#64748b', fontSize: 13, marginTop: 4 }}>
            Hard monetary limits, circuit breaker trip conditions, and append-only SQLite audit logs.
          </p>
        </div>
        <button 
          onClick={load}
          style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            color: '#334155',
            padding: '7px 14px',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 12,
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
          }}
        >
          <RotateCcw size={13} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div style={{ 
          background: '#fef2f2', 
          border: '1px solid #fecaca', 
          color: '#b91c1c', 
          padding: '10px 14px', 
          borderRadius: 6, 
          marginBottom: 16,
          fontSize: 13 
        }}>
          {error}
        </div>
      )}

      {/* KPI Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginBottom: 24 }}>
        <KpiCard 
          label="Single-Order Cap" 
          value={inr(limits.single_order_cap_inr ?? 50000)} 
          badgeText="HARD LIMIT"
          color="#2563eb"
          bg="#eff6ff"
          icon={ShieldCheck}
        />
        <KpiCard 
          label="Session Cap" 
          value={inr(limits.session_cap_inr ?? 200000)} 
          badgeText="24H WINDOW"
          color="#7c3aed"
          bg="#faf5ff"
          icon={Layers}
        />
        <KpiCard 
          label="Circuit Breaker" 
          value={`${limits.circuit_breaker_failure_threshold ?? 3} Failures`} 
          badgeText="FAIL-SAFE"
          color="#d97706"
          bg="#fffbeb"
          icon={AlertOctagon}
        />
        <KpiCard 
          label="Risk Threshold" 
          value={String(limits.risk_score_threshold ?? 0.7)} 
          badgeText="HUMAN REVIEW"
          color="#0284c7"
          bg="#f0f9ff"
          icon={Zap}
        />
        <KpiCard 
          label="Txns Processed" 
          value={String(metrics.transactions_processed ?? 0)} 
          badgeText="GATEWAY COUNT"
          color="#059669"
          bg="#ecfdf5"
          icon={Activity}
        />
        <KpiCard 
          label="Revenue Recovered" 
          value={inr(metrics.money_recovered_inr ?? 0)} 
          badgeText="AUTO SALVAGED"
          color="#059669"
          bg="#ecfdf5"
          icon={TrendingUp}
        />
        <KpiCard 
          label="Failure Rate" 
          value={`${((metrics.failure_rate ?? 0) * 100).toFixed(1)}%`} 
          badgeText="TRIAGED"
          color="#dc2626"
          bg="#fef2f2"
          icon={ShieldAlert}
        />
        <KpiCard 
          label="Recovery Links" 
          value={String(metrics.recovery_links_issued ?? 0)} 
          badgeText="DISPATCHED"
          color="#0284c7"
          bg="#f0f9ff"
          icon={RotateCcw}
        />
      </div>

      {/* Audit Log Table / Cards */}
      <div style={{ 
        background: '#ffffff', 
        border: '1px solid #e2e8f0', 
        borderRadius: 8, 
        padding: 20,
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Activity size={16} style={{ color: '#059669' }} />
            <h2 style={{ fontSize: 14, fontWeight: 700, margin: 0, color: '#0f172a' }}>Transaction Audit Logs</h2>
          </div>
          <span style={{ color: '#64748b', fontSize: 12 }}>
            Latest {traces.length} records · Immutable append-only store
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {traces.map((t) => (
            <details 
              key={t.id} 
              style={{ 
                background: '#ffffff', 
                border: '1px solid #e2e8f0', 
                borderRadius: 6, 
                padding: '10px 14px',
              }}
            >
              <summary style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, listStyle: 'none' }}>
                <span style={badge(t.status)}>{t.status}</span>
                <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: 13, color: '#0f172a' }}>
                  {t.tool_called || 'guardrail.check'}
                </span>
                <span style={{ color: '#64748b', fontSize: 12, fontFamily: 'var(--font-mono)' }}>{t.session_id}</span>
                <div style={{ flex: 1 }} />
                {t.latency_ms != null && (
                  <span style={{ color: '#64748b', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Clock size={11} />
                    {t.latency_ms} ms
                  </span>
                )}
                <span style={{ color: '#64748b', fontSize: 11 }}>{new Date(t.timestamp).toLocaleTimeString()}</span>
              </summary>

              {t.agent_reasoning && (
                <div style={{ 
                  color: '#334155', 
                  fontSize: 12, 
                  marginTop: 8, 
                  padding: '6px 10px', 
                  background: '#f8fafc', 
                  borderRadius: 4,
                  borderLeft: '3px solid #2563eb'
                }}>
                  {t.agent_reasoning}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 10 }}>
                <JsonBlock title="PAYLOAD SENT" data={t.payload_sent} />
                <JsonBlock title="API RESPONSE" data={t.api_response} />
              </div>
            </details>
          ))}

          {traces.length === 0 && (
            <div style={{ color: '#94a3b8', textAlign: 'center', padding: '24px 0', fontSize: 13 }}>
              No audit records stored yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function KpiCard({ 
  label, 
  value, 
  badgeText, 
  color,
  bg,
  icon: Icon
}: { 
  label: string; 
  value: string; 
  badgeText: string; 
  color: string;
  bg: string;
  icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
}) {
  return (
    <div style={{
      background: '#ffffff',
      border: '1px solid #e2e8f0',
      borderRadius: 8,
      padding: '16px 18px',
      boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ color: '#64748b', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.02em' }}>
          {label}
        </span>
        <Icon size={16} style={{ color }} />
      </div>

      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'Plus Jakarta Sans, sans-serif', color: '#0f172a', margin: '4px 0' }}>
        {value}
      </div>

      <div style={{
        fontSize: 10,
        fontWeight: 600,
        color,
        background: bg,
        display: 'inline-block',
        padding: '1px 6px',
        borderRadius: 4,
      }}>
        {badgeText}
      </div>
    </div>
  );
}

function JsonBlock({ title, data }: { title: string; data: unknown }) {
  return (
    <div>
      <div style={{ color: '#64748b', fontSize: 10, fontWeight: 600, letterSpacing: '0.02em', marginBottom: 3 }}>
        {title}
      </div>
      <pre style={{ 
        margin: 0, 
        background: '#f8fafc', 
        border: '1px solid #e2e8f0',
        borderRadius: 6, 
        padding: 8, 
        fontSize: 11, 
        fontFamily: 'var(--font-mono)',
        color: '#334155', 
        overflowX: 'auto', 
        maxHeight: 160 
      }}>
        {data == null ? 'null' : JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
