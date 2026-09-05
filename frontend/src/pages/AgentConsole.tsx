import { useCallback, useEffect, useRef, useState } from 'react';
import { 
  Bot, 
  Send, 
  RotateCcw, 
  Activity, 
  ShieldAlert, 
  Clock,
  Layers
} from 'lucide-react';
import { badge } from '../ui';

const API = '/api/v1';

type Role = 'user' | 'agent' | 'system';
interface ChatMsg {
  role: Role;
  text: string;
}
interface Trace {
  id: number;
  trace_id: string;
  timestamp: string;
  tool_called: string;
  status: string;
  latency_ms: number | null;
  agent_reasoning: string;
  payload_sent: unknown;
  api_response: unknown;
}

function newSessionId(): string {
  return 'sess_' + Math.random().toString(36).slice(2, 11);
}

export function AgentConsole() {
  const [sessionId, setSessionId] = useState<string>(newSessionId);
  const [messages, setMessages] = useState<ChatMsg[]>([
    { 
      role: 'system', 
      text: 'Connected to AgentSeva autonomous commerce agent (Claude 3.5 Sonnet). Financial guardrail limit is active (₹50,000 per order). Try asking: "Create an order for 2 packets of Aashirvaad Atta" or "Generate payment link for ₹450".' 
    },
  ]);
  const [input, setInput] = useState('');
  const [traces, setTraces] = useState<Trace[]>([]);
  const [busy, setBusy] = useState(false);
  const traceEndRef = useRef<HTMLDivElement | null>(null);

  const refreshTraces = useCallback(async () => {
    try {
      const res = await fetch(`${API}/audit/traces/${encodeURIComponent(sessionId)}`);
      if (res.ok) {
        setTraces(await res.json());
      } else if (res.status === 404) {
        setTraces([]);
      }
    } catch {
      /* backend not reachable yet */
    }
  }, [sessionId]);

  useEffect(() => {
    refreshTraces();
    const t = setInterval(refreshTraces, 2000);
    return () => clearInterval(t);
  }, [refreshTraces]);

  useEffect(() => {
    traceEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [traces]);

  const push = (role: Role, text: string) => setMessages((m) => [...m, { role, text }]);

  const send = async () => {
    const message = input.trim();
    if (!message || busy) return;
    setInput('');
    push('user', message);
    setBusy(true);
    try {
      const res = await fetch(`${API}/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: sessionId }),
      });
      const data = await res.json();
      if (res.ok) {
        if (data.session_id) setSessionId(data.session_id);
        push('agent', data.reply || '(no reply)');
        if (data.requires_escalation) {
          push('system', '⚠️ Financial Risk Escalation: High-value transaction held for human confirmation.');
        }
      } else {
        push('system', `⛔ ${data.detail || data.error || 'Request failed'}`);
      }
    } catch (e) {
      push('system', `⛔ Network error: ${String(e)}`);
    } finally {
      setBusy(false);
      refreshTraces();
    }
  };

  const simulateWebhook = async () => {
    const body = {
      event: 'payment.failed',
      payload: {
        payment: {
          entity: {
            id: 'pay_' + Math.random().toString(36).slice(2, 10),
            order_id: sessionId,
            amount: 250000,
            currency: 'INR',
            error_description: 'Customer bank server down - transaction failed',
            contact: '+919876543210',
            notes: { session_id: sessionId, customer_name: 'Aarav Sharma' },
          },
        },
      },
    };
    push('system', 'Simulating Razorpay webhook: payment.failed...');
    try {
      await fetch(`${API}/webhooks/razorpay`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      push('system', 'Revenue Recovery Engine engaged: Diagnosed root cause and issued retry link.');
    } catch (e) {
      push('system', `Simulation error: ${String(e)}`);
    }
    refreshTraces();
  };

  const simulateDropped = async () => {
    const body = {
      session_id: sessionId,
      order_id: sessionId,
      amount_inr: 1250,
      customer_name: 'Priya Patel',
      customer_phone: '+919123456789',
      last_stage: 'payment',
      idle_seconds: 180,
      payment_attempted: false,
    };
    push('system', 'Simulating dropped checkout session...');
    try {
      await fetch(`${API}/recovery/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      push('system', 'Dropped checkout salvaged: dynamic discount payment link created.');
    } catch (e) {
      push('system', `Simulation error: ${String(e)}`);
    }
    refreshTraces();
  };

  const resetSession = () => {
    const newId = newSessionId();
    setSessionId(newId);
    setTraces([]);
    setMessages([{ role: 'system', text: `Session refreshed. New session ID: ${newId}` }]);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', overflow: 'hidden', background: '#f8fafc' }}>
      {/* Sub-Header Actions */}
      <div 
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 24px',
          background: '#ffffff',
          borderBottom: '1px solid #e2e8f0',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: '#f1f5f9',
            border: '1px solid #e2e8f0',
            padding: '3px 8px',
            borderRadius: 5,
            fontSize: 12,
            color: '#334155',
            fontFamily: 'var(--font-mono)',
            fontWeight: 500,
          }}>
            <Layers size={13} style={{ color: '#64748b' }} />
            <span>SESSION: {sessionId}</span>
          </div>

          <span style={{ fontSize: 12, color: '#64748b' }}>
            Claude 3.5 Sonnet Tool-Use (Bounded 6 Steps / Turn)
          </span>
        </div>

        {/* Quick Simulation Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button 
            onClick={simulateWebhook}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              color: '#b91c1c',
              padding: '6px 12px',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
              boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
            }}
          >
            <ShieldAlert size={14} style={{ color: '#dc2626' }} />
            <span>Simulate Failed Payment</span>
          </button>

          <button 
            onClick={simulateDropped}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              color: '#b45309',
              padding: '6px 12px',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
              boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
            }}
          >
            <RotateCcw size={14} style={{ color: '#d97706' }} />
            <span>Simulate Dropped Cart</span>
          </button>

          <button 
            onClick={resetSession}
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              color: '#475569',
              padding: '6px 12px',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
              boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
            }}
          >
            New Session
          </button>
        </div>
      </div>

      {/* Dual View Workspace */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* LEFT PANE: Agent Chat */}
        <section 
          style={{ 
            flex: 1, 
            display: 'flex', 
            flexDirection: 'column', 
            borderRight: '1px solid #e2e8f0', 
            minWidth: 0,
            background: '#ffffff',
          }}
        >
          <div 
            style={{ 
              padding: '10px 18px', 
              borderBottom: '1px solid #e2e8f0', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'space-between',
              background: '#f8fafc',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Bot size={16} style={{ color: '#2563eb' }} />
              <span style={{ fontWeight: 600, fontSize: 13, color: '#0f172a' }}>Agent Conversation</span>
            </div>
            <span style={{ fontSize: 11, color: '#64748b' }}>
              Deterministic (temp = 0)
            </span>
          </div>

          {/* Messages Feed */}
          <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 12, background: '#f8fafc' }}>
            {messages.map((m, i) => (
              <div key={i} style={chatBubbleContainerStyle(m.role)}>
                <div style={chatBubbleHeaderStyle(m.role)}>
                  <span>{m.role.toUpperCase()}</span>
                </div>
                <div style={chatBubbleBodyStyle(m.role)}>
                  {m.text}
                </div>
              </div>
            ))}
            {busy && (
              <div style={chatBubbleContainerStyle('agent')}>
                <div style={chatBubbleHeaderStyle('agent')}>
                  <span>AGENT EVALUATING</span>
                </div>
                <div style={{ ...chatBubbleBodyStyle('agent'), display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="pulse-indicator" style={{ width: 6, height: 6, borderRadius: '50%', background: '#2563eb', display: 'inline-block' }} />
                  <span style={{ color: '#64748b' }}>Checking guardrails and preparing tool call...</span>
                </div>
              </div>
            )}
          </div>

          {/* Chat Input */}
          <div 
            style={{ 
              display: 'flex', 
              gap: 8, 
              padding: '12px 18px', 
              borderTop: '1px solid #e2e8f0',
              background: '#ffffff',
            }}
          >
            <input
              style={{
                flex: 1,
                padding: '9px 14px',
                borderRadius: 6,
                border: '1px solid #cbd5e1',
                background: '#ffffff',
                color: '#0f172a',
                fontSize: 13,
                outline: 'none',
                fontFamily: 'inherit',
                boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
              }}
              value={input}
              placeholder="e.g. 'Create an order for 2 packets of Aashirvaad Atta' or 'Generate link for ₹350'"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
              disabled={busy}
            />
            <button 
              onClick={send} 
              disabled={busy || !input.trim()}
              style={{
                padding: '0 16px',
                borderRadius: 6,
                border: '1px solid #2563eb',
                background: input.trim() && !busy ? '#2563eb' : '#94a3b8',
                color: '#ffffff',
                cursor: input.trim() && !busy ? 'pointer' : 'not-allowed',
                fontWeight: 600,
                fontSize: 13,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                transition: 'all 0.15s ease',
              }}
            >
              <Send size={14} />
              <span>Send</span>
            </button>
          </div>
        </section>

        {/* RIGHT PANE: Live Append-Only Audit Trail */}
        <section 
          style={{ 
            flex: 1.15, 
            display: 'flex', 
            flexDirection: 'column', 
            minWidth: 0, 
            background: '#ffffff' 
          }}
        >
          <div 
            style={{ 
              padding: '10px 18px', 
              borderBottom: '1px solid #e2e8f0', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'space-between',
              background: '#f8fafc',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Activity size={16} style={{ color: '#059669' }} />
              <span style={{ fontWeight: 600, fontSize: 13, color: '#0f172a' }}>Immutable Audit Trail</span>
              <span style={{
                fontSize: 11,
                fontWeight: 600,
                background: '#ecfdf5',
                color: '#059669',
                padding: '1px 6px',
                borderRadius: 4,
                border: '1px solid #a7f3d0'
              }}>
                {traces.length} Records
              </span>
            </div>
            <span style={{ fontSize: 11, color: '#64748b' }}>
              Auto-polled 2s · Append-Only SQLite
            </span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 10, background: '#f8fafc' }}>
            {traces.length === 0 && (
              <div style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                alignItems: 'center', 
                justifyContent: 'center', 
                height: '60%', 
                color: '#94a3b8',
                gap: 8,
                textAlign: 'center'
              }}>
                <Activity size={28} style={{ opacity: 0.3 }} />
                <div>
                  <div style={{ fontWeight: 600, color: '#475569', fontSize: 13 }}>No Audit Traces Recorded Yet</div>
                  <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
                    Trigger a chat action or click a simulation button to inspect the live decision tree.
                  </div>
                </div>
              </div>
            )}

            {traces.map((t, idx) => (
              <div 
                key={t.id || idx} 
                style={{ 
                  background: '#ffffff', 
                  border: '1px solid #e2e8f0', 
                  borderRadius: 8, 
                  padding: 12,
                  boxShadow: '0 1px 2px rgba(0, 0, 0, 0.04)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                  <span style={badge(t.status)}>
                    {t.status}
                  </span>

                  <span style={{ fontWeight: 600, fontSize: 13, color: '#0f172a', fontFamily: 'var(--font-mono)' }}>
                    {t.tool_called || 'guardrail.evaluate'}
                  </span>

                  <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#64748b' }}>
                    {t.latency_ms != null && (
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Clock size={11} />
                        {t.latency_ms} ms
                      </span>
                    )}
                    <span>{new Date(t.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>

                {t.agent_reasoning && (
                  <div style={{ 
                    fontSize: 12, 
                    color: '#334155', 
                    marginBottom: 8, 
                    padding: '6px 10px', 
                    background: '#f8fafc', 
                    borderRadius: 4,
                    borderLeft: '3px solid #2563eb'
                  }}>
                    <strong style={{ color: '#0f172a' }}>Reasoning:</strong> {t.agent_reasoning}
                  </div>
                )}

                <details style={{ marginTop: 2 }}>
                  <summary style={{ 
                    fontSize: 11, 
                    color: '#2563eb', 
                    cursor: 'pointer', 
                    fontWeight: 600,
                  }}>
                    View Structured Payload & Response
                  </summary>
                  <pre 
                    style={{ 
                      marginTop: 6,
                      padding: 8, 
                      borderRadius: 6, 
                      background: '#f8fafc', 
                      border: '1px solid #e2e8f0',
                      color: '#334155', 
                      fontSize: 11, 
                      fontFamily: 'var(--font-mono)',
                      overflowX: 'auto', 
                      maxHeight: 160,
                    }}
                  >
                    {JSON.stringify(t.api_response ?? t.payload_sent ?? {}, null, 2)}
                  </pre>
                </details>
              </div>
            ))}
            <div ref={traceEndRef} />
          </div>
        </section>
      </div>
    </div>
  );
}

function chatBubbleContainerStyle(role: Role): React.CSSProperties {
  if (role === 'user') {
    return {
      alignSelf: 'flex-end',
      maxWidth: '80%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'flex-end',
    };
  }
  if (role === 'agent') {
    return {
      alignSelf: 'flex-start',
      maxWidth: '82%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'flex-start',
    };
  }
  return {
    alignSelf: 'center',
    maxWidth: '90%',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  };
}

function chatBubbleHeaderStyle(role: Role): React.CSSProperties {
  return {
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: '0.02em',
    marginBottom: 3,
    color: role === 'user' ? '#2563eb' : role === 'agent' ? '#059669' : '#b45309',
  };
}

function chatBubbleBodyStyle(role: Role): React.CSSProperties {
  if (role === 'user') {
    return {
      background: '#2563eb',
      color: '#ffffff',
      padding: '10px 14px',
      borderRadius: '12px 12px 2px 12px',
      fontSize: 13,
      lineHeight: 1.45,
      boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
      wordBreak: 'break-word',
    };
  }
  if (role === 'agent') {
    return {
      background: '#ffffff',
      color: '#0f172a',
      border: '1px solid #e2e8f0',
      padding: '10px 14px',
      borderRadius: '12px 12px 12px 2px',
      fontSize: 13,
      lineHeight: 1.45,
      boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
      wordBreak: 'break-word',
    };
  }
  return {
    background: '#fffbeb',
    color: '#92400e',
    border: '1px solid #fde68a',
    padding: '7px 12px',
    borderRadius: 6,
    fontSize: 12,
    lineHeight: 1.4,
    textAlign: 'center',
  };
}
