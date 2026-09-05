import { useEffect, useState } from 'react';
import {
  Activity, Bot, Building2, ClipboardList, CreditCard,
  Package, RotateCcw, ShieldCheck, ShoppingCart, TrendingUp, Wifi
} from 'lucide-react';
import { CustomerDashboard } from './pages/CustomerDashboard';
import { AgentConsole } from './pages/AgentConsole';
import { SupervisorDashboard } from './pages/SupervisorDashboard';
import { OwnerDashboard } from './pages/OwnerDashboard';
import { StoreCatalog } from './pages/StoreCatalog';
import { AgenticCheckout } from './pages/AgenticCheckout';
import { OrdersRecovery } from './pages/OrdersRecovery';
import { AuditGuardrails } from './pages/AuditGuardrails';

export type AppTab = 'kiosk' | 'console' | 'supervisor' | 'owner' | 'checkout' | 'recovery' | 'audit' | 'catalog';
type Icon = React.ComponentType<{ size?: number; className?: string }>;
interface TabItem { key: AppTab; label: string; note: string; icon: Icon; }

const TABS: TabItem[] = [
  { key: 'console', label: 'Agent Console', note: 'Autonomous actions', icon: Bot },
  { key: 'kiosk', label: 'Store Kiosk', note: 'Customer counter', icon: ShoppingCart },
  { key: 'checkout', label: 'Direct Checkout', note: 'Payment initiation', icon: CreditCard },
  { key: 'recovery', label: 'Revenue Recovery', note: 'Save failed orders', icon: RotateCcw },
  { key: 'audit', label: 'Audit & Guardrails', note: 'Controls & traces', icon: ShieldCheck },
  { key: 'catalog', label: 'Catalog', note: 'Inventory registry', icon: Package },
  { key: 'supervisor', label: 'Order Dispatch', note: 'Fulfilment queue', icon: ClipboardList },
  { key: 'owner', label: 'Merchant Analytics', note: 'Business pulse', icon: TrendingUp },
];

function App() {
  const [tab, setTab] = useState<AppTab>('console');
  const [backendStatus, setBackendStatus] = useState<'ok' | 'connecting' | 'error'>('connecting');
  const [razorpayMode, setRazorpayMode] = useState('live');

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('/api/v1/health');
        if (!res.ok) throw new Error('health');
        const data = await res.json();
        setBackendStatus('ok');
        if (data.dependencies?.razorpay_mode) setRazorpayMode(data.dependencies.razorpay_mode);
      } catch { setBackendStatus('error'); }
    };
    check();
    const timer = window.setInterval(check, 10000);
    return () => window.clearInterval(timer);
  }, []);

  const active = TABS.find((item) => item.key === tab) ?? TABS[0];
  return (
    <div className="app-shell app-layout" style={{ minHeight: '100dvh', display: 'flex', overflow: 'hidden' }}>
      <aside className="app-rail" style={{ width: 238, flexShrink: 0, display: 'flex', flexDirection: 'column', padding: '22px 12px' }}>
        <div className="app-rail-brand" style={{ padding: '0 12px 24px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 10, background: '#e8b15a', color: '#17352f', display: 'grid', placeItems: 'center' }}>
            <Building2 size={18} />
          </div>
          <div className="app-header-copy">
            <div style={{ fontFamily: 'var(--font-heading)', fontSize: 18, fontWeight: 800, letterSpacing: '-.04em' }}>AgentSeva</div>
            <div style={{ color: '#a9c3bb', fontSize: 10, letterSpacing: '.04em' }}>MERCHANT OPERATIONS</div>
          </div>
        </div>
        <div className="eyebrow" style={{ color: '#76958b', padding: '0 12px 8px' }}>Workspace</div>
        <nav className="app-nav" style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {TABS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                data-active={tab === item.key}
                onClick={() => setTab(item.key)}
                title={item.note}
                style={{ border: 0, background: 'transparent', cursor: 'pointer', borderRadius: 9, padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 11, textAlign: 'left', transition: 'background .16s, color .16s', fontSize: 12, fontWeight: 600 }}
              >
                <Icon size={16} />
                <span className="app-nav-label">{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="app-rail-footer" style={{ marginTop: 'auto', padding: '14px 12px 0', borderTop: '1px solid rgba(255,255,255,.1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#a9c3bb' }}>
            <Activity size={14} color="#e8b15a" /> <span>Guardrails active</span>
          </div>
          <div style={{ color: '#76958b', fontSize: 10, marginTop: 5 }}>₹50,000 single-order cap</div>
        </div>
      </aside>
      <div className="app-main" style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: '100dvh' }}>
        <header style={{ minHeight: 66, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: '12px 26px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)' }}>
          <div>
            <div className="eyebrow">AgentSeva / {active.label}</div>
            <h1 style={{ margin: '3px 0 0', fontFamily: 'var(--font-heading)', fontSize: 19, color: 'var(--text-primary)', letterSpacing: '-.03em' }}>{active.label}</h1>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, border: '1px solid var(--border-color)', borderRadius: 7, padding: '6px 9px', color: 'var(--text-secondary)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
              <Wifi size={13} color={backendStatus === 'ok' ? '#177245' : '#9b6312'} />
              {backendStatus === 'ok' ? `RZP ${razorpayMode.toUpperCase()}` : backendStatus === 'error' ? 'API OFFLINE' : 'CONNECTING'}
            </div>
            <div style={{ width: 30, height: 30, borderRadius: '50%', background: '#dcebe4', color: '#17695e', display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 800 }}>RK</div>
          </div>
        </header>
        <main style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
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
    </div>
  );
}

export default App;