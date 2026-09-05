import { useCallback, useEffect, useState } from 'react';
import { 
  RotateCcw, 
  ExternalLink, 
  ShoppingBag, 
  User, 
  Phone, 
  Zap
} from 'lucide-react';
import { api, type Order } from '../api';
import { badge, inr } from '../ui';

export function OrdersRecovery() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setError('');
      setOrders(await api.listOrders());
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [load]);

  const recover = async (id: number) => {
    setBusyId(id);
    try {
      const res = await api.recover(id);
      const link = (res.recovery as { payment_link?: string }).payment_link;
      if (link) alert(`Revenue recovery link generated:\n${link}`);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div style={{ padding: '24px 32px', height: '100%', overflowY: 'auto', background: '#f8fafc', color: '#0f172a' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontFamily: 'Plus Jakarta Sans, sans-serif', fontSize: 20, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8, color: '#0c2340' }}>
            <RotateCcw size={20} style={{ color: '#2563eb' }} />
            Orders & Revenue Recovery
          </h1>
          <p style={{ color: '#64748b', fontSize: 13, marginTop: 4 }}>
            Monitor order lifecycles, diagnose payment drop-offs, and dispatch targeted recovery links.
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

      {orders.length === 0 && (
        <div style={{ 
          background: '#ffffff', 
          border: '1px solid #e2e8f0', 
          borderRadius: 8, 
          padding: 40,
          textAlign: 'center',
          color: '#64748b' 
        }}>
          <ShoppingBag size={32} style={{ opacity: 0.3, margin: '0 auto 8px' }} />
          <div style={{ fontWeight: 600, color: '#334155', fontSize: 14 }}>No Orders Recorded Yet</div>
          <div style={{ fontSize: 12, marginTop: 4, color: '#94a3b8' }}>
            Place an order via the Agent Console or Direct Checkout to see order tracking and recovery.
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {orders.map((o) => (
          <div 
            key={o.id} 
            style={{ 
              background: '#ffffff', 
              border: '1px solid #e2e8f0', 
              borderRadius: 8, 
              padding: '14px 18px',
              boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: 14, color: '#0f172a' }}>
                #{o.id}
              </span>
              <span style={badge(o.status)}>{o.status}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#475569', fontSize: 13 }}>
                <User size={13} />
                <span>{o.customer_name}</span>
                <span>·</span>
                <Phone size={13} />
                <span>{o.customer_phone}</span>
              </div>
              <div style={{ flex: 1 }} />
              <span style={{ fontSize: 18, fontWeight: 700, fontFamily: 'Plus Jakarta Sans, sans-serif', color: '#0f172a' }}>
                {inr(o.total_amount)}
              </span>
            </div>

            {/* Line items */}
            <div style={{ color: '#475569', fontSize: 12, marginTop: 8, padding: '6px 10px', background: '#f8fafc', borderRadius: 6 }}>
              {(o.items || []).map((it) => `${it.quantity}× ${it.name}`).join(', ') || 'Kirana items'}
            </div>

            {/* Gateway Telemetry */}
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8, fontSize: 11, color: '#64748b', fontFamily: 'var(--font-mono)' }}>
              {o.razorpay_order_id && <span>ORDER: {o.razorpay_order_id}</span>}
              {o.razorpay_payment_id && <span>PAYMENT: {o.razorpay_payment_id}</span>}
              {o.razorpay_payment_link_id && <span>LINK: {o.razorpay_payment_link_id}</span>}
              {o.created_at && <span>{new Date(o.created_at).toLocaleString()}</span>}
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10 }}>
              {o.payment_link && (
                <a 
                  href={o.payment_link} 
                  target="_blank" 
                  rel="noreferrer" 
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    background: '#ffffff',
                    border: '1px solid #e2e8f0',
                    color: '#2563eb',
                    padding: '5px 10px',
                    borderRadius: 5,
                    fontSize: 12,
                    fontWeight: 500,
                    textDecoration: 'none',
                  }}
                >
                  <ExternalLink size={12} />
                  <span>Open Payment Link</span>
                </a>
              )}

              {(o.status === 'failed' || o.status === 'pending') && (
                <button 
                  onClick={() => recover(o.id)} 
                  disabled={busyId === o.id}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    background: '#eff6ff',
                    border: '1px solid #bfdbfe',
                    color: '#1d4ed8',
                    padding: '5px 12px',
                    borderRadius: 5,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: busyId === o.id ? 'not-allowed' : 'pointer',
                  }}
                >
                  <Zap size={12} />
                  <span>{busyId === o.id ? 'Recovering...' : 'Trigger Recovery'}</span>
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
