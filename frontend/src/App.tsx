import { useState, useEffect } from 'react';
import { 
  Bot, 
  ShoppingCart, 
  ClipboardList, 
  TrendingUp, 
  RotateCcw, 
  ShieldCheck, 
  Package, 
  CreditCard,
  Building2
} from 'lucide-react';

import { CustomerDashboard } from './pages/CustomerDashboard';
import { AgentConsole } from './pages/AgentConsole';
import { SupervisorDashboard } from './pages/SupervisorDashboard';
import { OwnerDashboard } from './pages/OwnerDashboard';
import { StoreCatalog } from './pages/StoreCatalog';
import { AgenticCheckout } from './pages/AgenticCheckout';
import { OrdersRecovery } from './pages/OrdersRecovery';
import { AuditGuardrails } from './pages/AuditGuardrails';

export type AppTab = 
  | 'kiosk' 
  | 'console' 
  | 'supervisor' 
  | 'owner' 
  | 'checkout' 
  | 'recovery' 
  | 'audit' 
  | 'catalog';

interface TabItem {
  key: AppTab;
  label: string;
  badge?: string;
  icon: React.ComponentType<{ size?: number; className?: string; style?: React.CSSProperties }>;
}

const TABS: TabItem[] = [
  { key: 'console', label: 'Agent Console', badge: 'Claude 3.5', icon: Bot },
  { key: 'kiosk', label: 'Store Kiosk', icon: ShoppingCart },
  { key: 'checkout', label: 'Direct Checkout', icon: CreditCard },
  { key: 'recovery', label: 'Revenue Recovery', icon: RotateCcw },
  { key: 'audit', label: 'Audit & Guardrails', icon: ShieldCheck },
  { key: 'catalog', label: 'Catalog', icon: Package },
  { key: 'supervisor', label: 'Order Dispatch', icon: ClipboardList },
  { key: 'owner', label: 'Merchant Analytics', icon: TrendingUp },
];

function App() {
  const [tab, setTab] = useState<AppTab>('console');
  const [backendStatus, setBackendStatus] = useState<'ok' | 'connecting' | 'error'>('connecting');
  const [razorpayMode, setRazorpayMode] = useState<string>('live');

  // Check backend health
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch('/api/v1/health');
        if (res.ok) {
          const data = await res.json();
          setBackendStatus('ok');
          if (data.dependencies?.razorpay_mode) {
            setRazorpayMode(data.dependencies.razorpay_mode);
          }
        } else {
          setBackendStatus('error');
        }
      } catch {
        setBackendStatus('error');
      }
    };
    checkHealth();
    const timer = setInterval(checkHealth, 10000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div 
      style={{ 
        height: '100vh', 
        display: 'flex', 
        flexDirection: 'column', 
        overflow: 'hidden', 
        background: '#f8fafc',
        color: '#0f172a',
        fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
      }}
    >
      {/* Clean, authoritative SaaS Header */}
      <header 
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          padding: '10px 24px', 
          background: '#ffffff', 
          borderBottom: '1px solid #e2e8f0',
          zIndex: 50,
          gap: 16
        }}
      >
        {/* Brand & Subtitle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <div 
            style={{
              width: 32,
              height: 32,
              borderRadius: 6,
              background: '#0c2340',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff'
            }}
          >
            <Building2 size={18} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontFamily: 'Plus Jakarta Sans, sans-serif', fontWeight: 700, fontSize: 16, letterSpacing: '-0.02em', color: '#0c2340' }}>
                AgentSeva
              </span>
              <span style={{ 
                fontSize: 11, 
                fontWeight: 600, 
                background: '#eff6ff', 
                color: '#2563eb', 
                padding: '1px 6px', 
                borderRadius: 4,
                border: '1px solid #bfdbfe'
              }}>
                Razorpay Commerce Engine
              </span>
            </div>
            <div style={{ fontSize: 11, color: '#64748b' }}>
              Autonomous Payments & Recovery Engine
            </div>
          </div>
        </div>

        {/* Center Segmented Tabs */}
        <nav 
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 2, 
            background: '#f1f5f9', 
            padding: '3px', 
            borderRadius: 8,
            border: '1px solid #e2e8f0',
            overflowX: 'auto',
          }}
        >
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: active ? '1px solid #e2e8f0' : '1px solid transparent',
                  background: active ? '#ffffff' : 'transparent',
                  color: active ? '#0f172a' : '#64748b',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: active ? 600 : 500,
                  fontFamily: 'inherit',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap',
                  boxShadow: active ? '0 1px 2px rgba(0, 0, 0, 0.05)' : 'none',
                }}
              >
                <Icon size={14} style={{ color: active ? '#2563eb' : '#94a3b8' }} />
                <span>{t.label}</span>
                {t.badge && (
                  <span style={{
                    fontSize: 10,
                    fontWeight: 600,
                    background: active ? '#eff6ff' : '#e2e8f0',
                    color: active ? '#2563eb' : '#64748b',
                    padding: '1px 5px',
                    borderRadius: 4,
                  }}>
                    {t.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Right Telemetry */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          {/* Status Badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            padding: '4px 9px',
            borderRadius: 6,
            fontSize: 12,
            color: '#059669',
            fontWeight: 600,
          }}>
            <span 
              className={backendStatus === 'ok' ? 'pulse-indicator' : ''} 
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: backendStatus === 'ok' ? '#10b981' : '#f59e0b',
                display: 'inline-block'
              }} 
            />
            <span>{backendStatus === 'ok' ? `RPAY: ${razorpayMode.toUpperCase()}` : 'CONNECTING'}</span>
          </div>

          {/* Financial Guardrail Pill */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            padding: '4px 9px',
            borderRadius: 6,
            fontSize: 12,
            color: '#334155',
            fontWeight: 600,
          }}>
            <ShieldCheck size={14} style={{ color: '#2563eb' }} />
            <span>₹50K Cap</span>
          </div>
        </div>
      </header>

      {/* Main View Area */}
      <main style={{ flex: 1, minHeight: 0, overflow: 'hidden', position: 'relative', background: '#f8fafc' }}>
        {tab === 'console' && <AgentConsole />}
        {tab === 'kiosk' && <CustomerDashboard />}
        {tab === 'checkout' && <AgenticCheckout />}
        {tab === 'recovery' && <OrdersRecovery />}
        {tab === 'audit' && <AuditGuardrails />}
        {tab === 'catalog' && <StoreCatalog />}
        {tab === 'supervisor' && <SupervisorDashboard />}
        {tab === 'owner' && <OwnerDashboard />}
      </main>
    </div>
  );
}

export default App;
