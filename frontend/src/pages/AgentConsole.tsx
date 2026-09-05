import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import {
  Activity,
  ArrowUpRight,
  Bot,
  ChevronDown,
  Clock3,
  FileCheck2,
  Layers3,
  MessageSquare,
  Mic,
  MicOff,
  RotateCcw,
  Send,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Terminal,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { badge } from '../ui';
import { readJsonResponse } from '../api';

const API = '/api/v1';

type Role = 'user' | 'agent' | 'system';
interface ChatMsg { role: Role; text: string; }
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

const prompts = [
  { label: 'Create an order', prompt: 'Create an order for 2 packets of Aashirvaad Atta', icon: Layers3 },
  { label: 'Make a payment link', prompt: 'Generate payment link for ₹450', icon: ArrowUpRight },
  { label: 'Check a risky amount', prompt: 'Can I create an order for ₹52,000?', icon: ShieldCheck },
];

export function AgentConsole() {
  const [sessionId, setSessionId] = useState<string>(newSessionId);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [traces, setTraces] = useState<Trace[]>([]);
  const [busy, setBusy] = useState(false);
  const [hasAuditActivity, setHasAuditActivity] = useState(false);
  const [simulating, setSimulating] = useState<'payment' | 'cart' | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [voiceReplies, setVoiceReplies] = useState(true);
  const [voiceSupported] = useState(
    () => typeof window !== 'undefined'
      && Boolean((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition),
  );
  const traceEndRef = useRef<HTMLDivElement | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<any>(null);

  const refreshTraces = useCallback(async () => {
    try {
      const res = await fetch(`${API}/audit/traces/${encodeURIComponent(sessionId)}`);
      if (res.ok) setTraces(await res.json());
      else if (res.status === 404) setTraces([]);
    } catch { /* backend not reachable yet */ }
  }, [sessionId]);

  useEffect(() => {
    if (!hasAuditActivity) return;
    refreshTraces();
    const timer = setInterval(refreshTraces, 2000);
    return () => clearInterval(timer);
  }, [hasAuditActivity, refreshTraces]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    traceEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, traces]);

  const push = (role: Role, text: string) => setMessages((current) => [...current, { role, text }]);

  const speak = useCallback((text: string) => {
    if (!voiceReplies || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-IN';
    utterance.rate = 1;
    window.speechSynthesis.speak(utterance);
  }, [voiceReplies]);

  useEffect(() => () => {
    recognitionRef.current?.stop();
    window.speechSynthesis?.cancel();
  }, []);

  const send = async (preset?: string) => {
    const message = (preset ?? input).trim();
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
      const data = await readJsonResponse<{
        session_id?: string;
        reply?: string;
        requires_escalation?: boolean;
        detail?: string;
        error?: string;
      }>(res);
      if (res.ok) {
        if (data?.session_id) setSessionId(data.session_id);
        setHasAuditActivity(true);
        const reply = data?.reply || '(no reply)';
        push('agent', reply);
        speak(reply);
        if (data?.requires_escalation) push('system', 'Financial risk escalation: this transaction is held for human confirmation.');
      } else push('system', `Request failed: ${data?.detail || data?.error || 'Unknown error'}`);
    } catch (error) {
      push('system', `Network error: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  };

  const toggleListening = () => {
    if (!voiceSupported || busy) return;
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }

    const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new Recognition();
    recognition.lang = 'en-IN';
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => setIsListening(true);
    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results)
        .map((result: any) => result[0]?.transcript || '')
        .join(' ')
        .trim();
      setInput(transcript);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    recognitionRef.current = recognition;
    recognition.start();
  };

  const simulateWebhook = async () => {
    setSimulating('payment');
    const body = {
      event: 'payment.failed',
      payload: { payment: { entity: {
        id: 'pay_' + Math.random().toString(36).slice(2, 10), order_id: sessionId, amount: 250000, currency: 'INR',
        error_description: 'Customer bank server down - transaction failed', contact: '+919876543210',
        notes: { session_id: sessionId, customer_name: 'Aarav Sharma' },
      } } },
    };
    push('system', 'Simulating Razorpay webhook: payment.failed');
    try {
      const res = await fetch(`${API}/webhooks/razorpay`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      setHasAuditActivity(true);
      push('system', 'Revenue Recovery Engine engaged: diagnosed root cause and issued retry link.');
    } catch (error) { push('system', `Simulation error: ${String(error)}`); }
    finally { setSimulating(null); }
  };

  const simulateDropped = async () => {
    setSimulating('cart');
    const body = {
      session_id: sessionId, order_id: sessionId, amount_inr: 1250, customer_name: 'Priya Patel',
      customer_phone: '+919123456789', last_stage: 'payment', idle_seconds: 180, payment_attempted: false,
    };
    push('system', 'Simulating dropped checkout session');
    try {
      const res = await fetch(`${API}/recovery/checkout`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      setHasAuditActivity(true);
      push('system', 'Dropped checkout salvaged: dynamic discount payment link created.');
    } catch (error) { push('system', `Simulation error: ${String(error)}`); }
    finally { setSimulating(null); }
  };

  const resetSession = () => {
    const next = newSessionId();
    setSessionId(next);
    setTraces([]);
    setHasAuditActivity(false);
    setMessages([]);
    setInput('');
    recognitionRef.current?.stop();
    window.speechSynthesis?.cancel();
  };

  const submit = (event: FormEvent) => { event.preventDefault(); void send(); };

  return (
    <div className="console-page">
      <div className="console-toolbar">
        <div className="console-session">
          <span className="console-live-dot" />
          <span className="eyebrow">Live session</span>
          <code>{sessionId}</code>
        </div>
        <div className="console-toolbar-meta">
          <span className="model-chip"><Sparkles size={13} /> Qwen3-32B · Hugging Face</span>
          <button className="console-quiet-action" onClick={resetSession}><RotateCcw size={14} /> New session</button>
        </div>
      </div>

      <div className="console-grid">
        <section className="conversation-panel">
          <div className="panel-heading">
            <div className="panel-heading-icon teal"><Bot size={17} /></div>
            <div>
              <h2>Commerce copilot</h2>
              <p>Speak or type an order. Review it, then send safely.</p>
            </div>
            <span className={`status-pill ${isListening ? 'listening' : ''}`}><span /> {isListening ? 'Listening' : busy ? 'Working' : 'Ready'}</span>
          </div>

          <div className="message-feed">
            {messages.length === 0 ? (
              <div className="welcome-state">
                <div className="welcome-mark"><MessageSquare size={22} /></div>
                <span className="eyebrow">AgentSeva is ready</span>
                <h3>What should we do for your customer?</h3>
                <p>Speak or type a commerce task in plain language. Your transcript stays editable, and every action is checked against the ₹50,000 order limit.</p>
                <div className="prompt-list">
                  {prompts.map(({ label, prompt, icon: Icon }) => (
                    <button key={label} className="prompt-card" onClick={() => void send(prompt)} disabled={busy}>
                      <span className="prompt-icon"><Icon size={15} /></span>
                      <span><strong>{label}</strong><small>{prompt}</small></span>
                      <ArrowUpRight size={14} />
                    </button>
                  ))}
                </div>
              </div>
            ) : messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`message-row ${message.role}`}>
                {message.role === 'agent' && <div className="message-avatar"><Bot size={15} /></div>}
                <div className="message-stack">
                  <span className="message-label">{message.role === 'agent' ? 'AGENTSEVA' : message.role === 'user' ? 'YOU' : 'EVENT'}</span>
                  <div className="message-bubble">{message.text}</div>
                </div>
              </div>
            ))}
            {busy && (
              <div className="message-row agent">
                <div className="message-avatar"><Bot size={15} /></div>
                <div className="message-stack">
                  <span className="message-label">AGENTSEVA · WORKING</span>
                  <div className="message-bubble thinking"><span /><span /><span /> Checking the guardrails and preparing the action</div>
                </div>
              </div>
            )}
            <div ref={messageEndRef} />
          </div>

          <form className="composer" onSubmit={submit}>
            <button
              className={`voice-button ${isListening ? 'active' : ''}`}
              type="button"
              onClick={toggleListening}
              disabled={!voiceSupported || busy}
              aria-label={isListening ? 'Stop listening' : 'Start voice input'}
              title={voiceSupported ? (isListening ? 'Stop listening' : 'Speak your order') : 'Voice input is not supported in this browser'}
            >
              {isListening ? <MicOff size={17} /> : <Mic size={17} />}
            </button>
            <div className="composer-field">
              <textarea value={input} onChange={(event) => setInput(event.target.value)} disabled={busy} rows={1}
                placeholder={isListening ? 'Listening… speak your order' : 'Ask for an order, payment link, or recovery action…'} onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send(); }
                }} />
              <span className="composer-hint">Enter to send · Shift + Enter for a new line</span>
            </div>
            <button className="send-button" type="submit" disabled={busy || !input.trim()} aria-label="Send message">
              <Send size={16} />
            </button>
          </form>
          <div className="composer-foot">
            <span><ShieldCheck size={13} /> Financial actions are evaluated before execution</span>
            <button type="button" onClick={() => {
              setVoiceReplies((enabled) => {
                if (enabled) window.speechSynthesis?.cancel();
                return !enabled;
              });
            }} aria-label={voiceReplies ? 'Mute spoken replies' : 'Enable spoken replies'}>
              {voiceReplies ? <Volume2 size={13} /> : <VolumeX size={13} />}
              {voiceReplies ? 'Spoken replies on' : 'Spoken replies off'}
            </button>
          </div>
        </section>

        <aside className="audit-panel">
          <div className="panel-heading audit-heading">
            <div className="panel-heading-icon ink"><FileCheck2 size={17} /></div>
            <div><h2>Decision ledger</h2><p>Every tool call, held in sequence.</p></div>
            <span className="record-count">{traces.length} {traces.length === 1 ? 'record' : 'records'}</span>
          </div>
          <div className="audit-actions">
            <button onClick={() => void simulateWebhook()} disabled={simulating !== null}>
              <ShieldAlert size={14} /> {simulating === 'payment' ? 'Simulating…' : 'Failed payment'}
            </button>
            <button onClick={() => void simulateDropped()} disabled={simulating !== null}>
              <RotateCcw size={14} /> {simulating === 'cart' ? 'Simulating…' : 'Dropped cart'}
            </button>
          </div>
          <div className="audit-feed">
            {traces.length === 0 ? (
              <div className="audit-empty">
                <div className="empty-ledger"><Terminal size={19} /></div>
                <h3>The ledger is quiet</h3>
                <p>Send a request or run a recovery simulation. The agent’s action, guardrail decision, and response will appear here.</p>
                <div className="audit-steps">
                  <span><i>01</i> Request received</span>
                  <span><i>02</i> Guardrail evaluated</span>
                  <span><i>03</i> Action recorded</span>
                </div>
              </div>
            ) : traces.map((trace, index) => (
              <div className="trace-card" key={trace.id || index}>
                <div className="trace-topline">
                  <span className="trace-index">{String(index + 1).padStart(2, '0')}</span>
                  <span style={badge(trace.status)}>{trace.status}</span>
                  <code>{trace.tool_called || 'guardrail.evaluate'}</code>
                  <span className="trace-time">{trace.latency_ms != null && <><Clock3 size={11} />{trace.latency_ms}ms · </>}{new Date(trace.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
                {trace.agent_reasoning && <p className="trace-reasoning">{trace.agent_reasoning}</p>}
                <details><summary>View payload <ChevronDown size={13} /></summary>
                  <pre>{JSON.stringify(trace.api_response ?? trace.payload_sent ?? {}, null, 2)}</pre>
                </details>
              </div>
            ))}
            <div ref={traceEndRef} />
          </div>
          <div className="audit-footer"><Activity size={13} /> Auto-polling every 2 seconds <span>·</span> append-only</div>
        </aside>
      </div>
    </div>
  );
}
