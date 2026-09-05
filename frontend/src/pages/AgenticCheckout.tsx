import { useEffect, useMemo, useState } from 'react';
import { 
  CreditCard, 
  Send, 
  Bot, 
  ExternalLink, 
  Plus, 
  CheckCircle2
} from 'lucide-react';
import { api, type Product } from '../api';
import { inr } from '../ui';

type Role = 'user' | 'agent' | 'system';
interface Msg { role: Role; text: string; }
interface CartLine { product: Product; qty: number; }

function newSession(): string {
  return 'chat_' + Math.random().toString(36).slice(2, 11);
}

export function AgenticCheckout() {
  const [sessionId, setSessionId] = useState(newSession);
  const [messages, setMessages] = useState<Msg[]>([
    { 
      role: 'system', 
      text: 'Ask the assistant for kirana product recommendations, or select items on the right and trigger autonomous Razorpay checkout.' 
    },
  ]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  const [products, setProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [checkoutLink, setCheckoutLink] = useState<string | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.listProducts().then(setProducts).catch(() => {});
  }, []);

  const total = useMemo(() => cart.reduce((s, l) => s + l.product.price_inr * l.qty, 0), [cart]);

  const addToCart = (p: Product) => {
    setCart((c) => {
      const existing = c.find((l) => l.product.id === p.id);
      if (existing) return c.map((l) => (l.product.id === p.id ? { ...l, qty: l.qty + 1 } : l));
      return [...c, { product: p, qty: 1 }];
    });
  };

  const setQty = (id: number, qty: number) =>
    setCart((c) => c.flatMap((l) => (l.product.id === id ? (qty > 0 ? [{ ...l, qty }] : []) : [l])));

  const push = (role: Role, t: string) => setMessages((m) => [...m, { role, text: t }]);

  const send = async () => {
    const message = text.trim();
    if (!message || busy) return;
    setText('');
    push('user', message);
    setBusy(true);
    try {
      const data = await api.chat(message, sessionId);
      if (data.session_id) setSessionId(data.session_id);
      push('agent', data.reply || '(no reply)');
      if (data.requires_escalation) {
        push('system', '⚠️ Requires human confirmation / escalation.');
      }
    } catch (e) {
      push('system', `⛔ ${String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const checkout = async () => {
    setError('');
    setCheckoutLink(null);
    if (!name || phone.length < 8 || cart.length === 0) {
      setError('Please provide customer name, a valid phone number, and at least one item.');
      return;
    }
    try {
      const res = await api.checkout({
        customer_name: name, 
        customer_phone: phone,
        items: cart.map((l) => ({ product_id: l.product.id, quantity: l.qty })),
      });
      setCheckoutLink(res.payment_link);
      push('system', `🧾 Razorpay payment link generated for ${inr(res.total_inr)} → ${res.payment_link}`);
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div style={{ display: 'flex', height: '100%', minHeight: 0, width: '100%', overflow: 'hidden', background: '#f8fafc' }}>
      {/* LEFT: AI Shopping Assistant */}
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Bot size={16} style={{ color: '#2563eb' }} />
            <span style={{ fontWeight: 600, fontSize: 13, color: '#0f172a' }}>AI Shopping Concierge</span>
          </div>
          <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'var(--font-mono)' }}>
            {sessionId}
          </span>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 18, display: 'flex', flexDirection: 'column', gap: 12, background: '#f8fafc' }}>
          {messages.map((m, i) => (
            <div key={i} style={chatBubbleContainer(m.role)}>
              <div style={{ fontSize: 10, fontWeight: 600, marginBottom: 2, color: m.role === 'user' ? '#2563eb' : m.role === 'agent' ? '#059669' : '#b45309' }}>
                {m.role.toUpperCase()}
              </div>
              <div style={chatBubbleStyle(m.role)}>{m.text}</div>
            </div>
          ))}
          {busy && (
            <div style={chatBubbleContainer('agent')}>
              <div style={{ fontSize: 10, fontWeight: 600, marginBottom: 2, color: '#059669' }}>AGENT</div>
              <div style={{ ...chatBubbleStyle('agent'), display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="pulse-indicator" style={{ width: 6, height: 6, borderRadius: '50%', background: '#2563eb', display: 'inline-block' }} />
                <span style={{ color: '#64748b' }}>Thinking...</span>
              </div>
            </div>
          )}
        </div>

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
            value={text} 
            placeholder='e.g. "What organic staples do you have under ₹200?"'
            onChange={(e) => setText(e.target.value)} 
            onKeyDown={(e) => e.key === 'Enter' && send()} 
            disabled={busy} 
          />
          <button 
            onClick={send} 
            disabled={busy || !text.trim()}
            style={{
              padding: '0 16px',
              borderRadius: 6,
              border: '1px solid #2563eb',
              background: text.trim() && !busy ? '#2563eb' : '#94a3b8',
              color: '#ffffff',
              cursor: text.trim() && !busy ? 'pointer' : 'not-allowed',
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

      {/* RIGHT: Cart & Razorpay Checkout */}
      <section 
        style={{ 
          flex: 1.1, 
          display: 'flex', 
          flexDirection: 'column', 
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <CreditCard size={16} style={{ color: '#059669' }} />
            <span style={{ fontWeight: 600, fontSize: 13, color: '#0f172a' }}>Order Basket & Razorpay Link</span>
          </div>
          <span style={{ fontSize: 11, color: '#64748b' }}>
            Guardrail Protected
          </span>
        </div>

        <div style={{ padding: 18, overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 16, background: '#f8fafc' }}>
          {/* Quick Product Adder */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', letterSpacing: '0.02em', marginBottom: 6, textTransform: 'uppercase' }}>
              Click to quick-add to basket:
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {products.slice(0, 8).map((p) => (
                <button 
                  key={p.id} 
                  onClick={() => addToCart(p)}
                  disabled={!p.in_stock}
                  style={{
                    padding: '5px 10px',
                    borderRadius: 6,
                    border: '1px solid #e2e8f0',
                    background: '#ffffff',
                    color: p.in_stock ? '#334155' : '#94a3b8',
                    cursor: p.in_stock ? 'pointer' : 'not-allowed',
                    fontSize: 12,
                    fontWeight: 500,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 5,
                    transition: 'all 0.15s ease',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                  }}
                >
                  <Plus size={11} style={{ color: '#2563eb' }} />
                  <span>{p.name.split('(')[0].trim()}</span>
                  <span style={{ color: '#059669', fontWeight: 600 }}>{inr(p.price_inr)}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Cart Items List */}
          <div style={{ 
            background: '#ffffff', 
            border: '1px solid #e2e8f0', 
            borderRadius: 8, 
            padding: 16,
            boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10, display: 'flex', justifyContent: 'space-between', color: '#0f172a' }}>
              <span>Items ({cart.length})</span>
              <span style={{ color: '#0f172a', fontSize: 16, fontWeight: 700, fontFamily: 'Plus Jakarta Sans, sans-serif' }}>Total: {inr(total)}</span>
            </div>

            {cart.length === 0 && (
              <div style={{ color: '#94a3b8', fontSize: 13, textAlign: 'center', padding: '16px 0' }}>
                Your checkout basket is empty. Click items above to add.
              </div>
            )}

            {cart.map((l) => (
              <div 
                key={l.product.id} 
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'space-between',
                  padding: '8px 0', 
                  borderBottom: '1px solid #f1f5f9',
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#0f172a' }}>{l.product.name}</div>
                  <div style={{ color: '#64748b', fontSize: 11 }}>{inr(l.product.price_inr)} each</div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button 
                    onClick={() => setQty(l.product.id, l.qty - 1)}
                    style={{ 
                      background: '#f1f5f9', 
                      border: '1px solid #e2e8f0', 
                      color: '#334155', 
                      width: 24, 
                      height: 24, 
                      borderRadius: 4, 
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 14,
                      fontWeight: 600,
                    }}
                  >
                    −
                  </button>
                  <span style={{ fontWeight: 600, fontSize: 13, minWidth: 18, textAlign: 'center', color: '#0f172a' }}>{l.qty}</span>
                  <button 
                    onClick={() => setQty(l.product.id, l.qty + 1)}
                    style={{ 
                      background: '#f1f5f9', 
                      border: '1px solid #e2e8f0', 
                      color: '#334155', 
                      width: 24, 
                      height: 24, 
                      borderRadius: 4, 
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 14,
                      fontWeight: 600,
                    }}
                  >
                    +
                  </button>
                  <div style={{ width: 70, textAlign: 'right', fontWeight: 600, color: '#0f172a', fontSize: 13 }}>
                    {inr(l.product.price_inr * l.qty)}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Customer Details Form */}
          <div style={{ 
            background: '#ffffff', 
            border: '1px solid #e2e8f0', 
            borderRadius: 8, 
            padding: 16,
            boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', letterSpacing: '0.02em', textTransform: 'uppercase' }}>
              Customer Information
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <input 
                style={{
                  padding: '9px 14px',
                  borderRadius: 6,
                  border: '1px solid #cbd5e1',
                  background: '#ffffff',
                  color: '#0f172a',
                  fontSize: 13,
                  outline: 'none',
                  fontFamily: 'inherit',
                }}
                placeholder="Customer Name (e.g. Aarav)" 
                value={name} 
                onChange={(e) => setName(e.target.value)} 
              />
              <input 
                style={{
                  padding: '9px 14px',
                  borderRadius: 6,
                  border: '1px solid #cbd5e1',
                  background: '#ffffff',
                  color: '#0f172a',
                  fontSize: 13,
                  outline: 'none',
                  fontFamily: 'inherit',
                }}
                placeholder="Mobile (+919876543210)" 
                value={phone} 
                onChange={(e) => setPhone(e.target.value)} 
              />
            </div>

            <button 
              onClick={checkout} 
              disabled={cart.length === 0}
              style={{
                marginTop: 4,
                padding: '10px 18px',
                borderRadius: 6,
                border: 'none',
                background: cart.length > 0 ? '#059669' : '#94a3b8',
                color: '#ffffff',
                cursor: cart.length > 0 ? 'pointer' : 'not-allowed',
                fontWeight: 600,
                fontSize: 13,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                boxShadow: cart.length > 0 ? '0 1px 3px rgba(5, 150, 105, 0.3)' : 'none',
              }}
            >
              <CreditCard size={15} />
              <span>Generate Razorpay Payment Link ({inr(total)})</span>
            </button>

            {error && (
              <div style={{ 
                color: '#b91c1c', 
                fontSize: 12, 
                marginTop: 4, 
                background: '#fef2f2', 
                border: '1px solid #fecaca', 
                padding: '6px 10px', 
                borderRadius: 4 
              }}>
                ⛔ {error}
              </div>
            )}

            {checkoutLink && (
              <div style={{ 
                marginTop: 6, 
                padding: 12, 
                background: '#ecfdf5', 
                border: '1px solid #a7f3d0', 
                borderRadius: 6,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#059669', fontWeight: 600, fontSize: 12 }}>
                  <CheckCircle2 size={14} />
                  <span>Razorpay Link Ready:</span>
                </div>
                <a 
                  href={checkoutLink} 
                  target="_blank" 
                  rel="noreferrer" 
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 5, 
                    color: '#2563eb', 
                    fontSize: 12, 
                    marginTop: 6, 
                    wordBreak: 'break-all',
                    fontWeight: 500,
                  }}
                >
                  <ExternalLink size={12} />
                  <span>{checkoutLink}</span>
                </a>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function chatBubbleContainer(role: Role): React.CSSProperties {
  if (role === 'user') {
    return { alignSelf: 'flex-end', maxWidth: '80%', display: 'flex', flexDirection: 'column', alignItems: 'flex-end' };
  }
  if (role === 'agent') {
    return { alignSelf: 'flex-start', maxWidth: '82%', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' };
  }
  return { alignSelf: 'center', maxWidth: '90%', display: 'flex', flexDirection: 'column', alignItems: 'center' };
}

function chatBubbleStyle(role: Role): React.CSSProperties {
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
