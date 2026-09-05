import React, { useState } from 'react';
import type { Order } from '../stores/kioskStore';
import { useKioskStore } from '../stores/kioskStore';
import { 
  ClipboardList, 
  AlertTriangle, 
  Hourglass, 
  Search,
  Scan,
  Check,
  ChevronRight,
  Package
} from 'lucide-react';

export const SupervisorDashboard: React.FC = () => {
  const { 
    orders, 
    updateOrderStatus, 
    products, 
    setProducts 
  } = useKioskStore();

  const [searchBarcode, setSearchBarcode] = useState('');
  const [scanResult, setScanResult] = useState<any>(null);
  const [stockEditValue, setStockEditValue] = useState<number>(0);
  const [showStockCheckAlert, setShowStockCheckAlert] = useState(false);

  // Expiring soon items (expiry within 7 days from June 4, 2026)
  const expiringItems = products.filter(p => p.expiry && new Date(p.expiry) <= new Date('2026-06-11'));
  
  // Low stock items (stock < 20)
  const lowStockItems = products.filter(p => p.stock < 20);

  // Status updates
  const advanceStatus = (orderId: string, currentStatus: Order['status']) => {
    let nextStatus: Order['status'] = currentStatus;
    if (currentStatus === 'pending') nextStatus = 'preparing';
    else if (currentStatus === 'preparing') nextStatus = 'ready';
    else if (currentStatus === 'ready') nextStatus = 'completed';
    
    updateOrderStatus(orderId, nextStatus);
  };

  // Simulate scanning a barcode
  const handleBarcodeSearch = () => {
    const prod = products.find(p => p.barcode === searchBarcode || p.name.toLowerCase().includes(searchBarcode.toLowerCase()));
    if (prod) {
      setScanResult(prod);
      setStockEditValue(prod.stock);
    } else {
      setScanResult(null);
      alert('Product not found in inventory registry.');
    }
  };

  const handleUpdateStock = () => {
    if (!scanResult) return;
    const updated = products.map(p => 
      p.id === scanResult.id ? { ...p, stock: stockEditValue } : p
    );
    setProducts(updated);
    setScanResult({ ...scanResult, stock: stockEditValue });
    setShowStockCheckAlert(true);
    setTimeout(() => setShowStockCheckAlert(false), 2000);
  };

  const statusBadge = (status: string): React.CSSProperties => {
    const map: Record<string, { bg: string; color: string; border: string }> = {
      pending: { bg: '#f8fafc', color: '#64748b', border: '#e2e8f0' },
      preparing: { bg: '#fffbeb', color: '#b45309', border: '#fde68a' },
      ready: { bg: '#eff6ff', color: '#2563eb', border: '#bfdbfe' },
      completed: { bg: '#ecfdf5', color: '#059669', border: '#a7f3d0' },
    };
    const s = map[status] || map.pending;
    return {
      fontSize: 11,
      fontWeight: 600,
      padding: '2px 8px',
      borderRadius: 4,
      background: s.bg,
      color: s.color,
      border: `1px solid ${s.border}`,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.02em',
    };
  };

  const nextLabel = (status: string) => {
    if (status === 'pending') return 'Start Preparing';
    if (status === 'preparing') return 'Mark Ready';
    if (status === 'ready') return 'Complete Order';
    return '';
  };

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 340px',
      height: '100%',
      overflow: 'hidden',
      background: '#f8fafc',
    }}>
      {/* Active Orders List */}
      <main style={{ padding: '24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div>
          <h1 style={{ 
            fontSize: 20, 
            margin: 0, 
            fontFamily: 'Plus Jakarta Sans, sans-serif', 
            fontWeight: 700, 
            color: '#0c2340',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <ClipboardList size={20} style={{ color: '#2563eb' }} />
            Counter & Order Queue
          </h1>
          <p style={{ color: '#64748b', fontSize: 13, marginTop: 4 }}>
            Monitor self-service orders, dispatch helper staff, and manage pickup statuses.
          </p>
        </div>

        {/* Orders Grid */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {orders.map((order) => (
            <div 
              key={order.id} 
              style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: 16,
                boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ 
                    fontSize: 14, 
                    fontWeight: 700, 
                    color: '#0f172a',
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {order.id}
                  </span>
                  <span style={{ 
                    fontSize: 11, 
                    background: order.type === 'assisted' ? '#fffbeb' : '#eff6ff',
                    color: order.type === 'assisted' ? '#b45309' : '#2563eb',
                    border: `1px solid ${order.type === 'assisted' ? '#fde68a' : '#bfdbfe'}`,
                    padding: '1px 7px',
                    borderRadius: 4,
                    fontWeight: 600,
                  }}>
                    {order.type === 'assisted' ? 'Assisted' : 'Self Service'}
                  </span>
                </div>
                <span style={statusBadge(order.status)}>
                  {order.status}
                </span>
              </div>

              {/* Items */}
              <div style={{ 
                background: '#f8fafc', 
                borderRadius: 6, 
                padding: '8px 12px', 
                marginBottom: 10,
                display: 'flex', 
                flexDirection: 'column', 
                gap: 4 
              }}>
                {order.items.map((item, idx) => (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ fontWeight: 500, color: '#0f172a' }}>
                      {item.product.name} <span style={{ color: '#64748b' }}>×{item.quantity}</span>
                    </span>
                    <span style={{ color: '#64748b', fontSize: 12 }}>Aisle: {item.product.location}</span>
                  </div>
                ))}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontSize: 12, color: '#475569' }}>
                  Customer: <strong style={{ color: '#0f172a' }}>{order.customerName}</strong> ({order.phone})
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontWeight: 700, fontSize: 15, color: '#0f172a', fontFamily: 'Plus Jakarta Sans, sans-serif' }}>
                    ₹{order.total}
                  </span>
                  
                  {order.status !== 'completed' && (
                    <button 
                      onClick={() => advanceStatus(order.id, order.status)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 5,
                        background: '#2563eb',
                        color: '#ffffff',
                        border: 'none',
                        padding: '6px 12px',
                        borderRadius: 6,
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
                      }}
                    >
                      <span>{nextLabel(order.status)}</span>
                      <ChevronRight size={13} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {orders.length === 0 && (
            <div style={{ 
              background: '#ffffff', 
              border: '1px solid #e2e8f0', 
              borderRadius: 8, 
              textAlign: 'center', 
              padding: 40, 
              color: '#94a3b8' 
            }}>
              <Package size={28} style={{ opacity: 0.3, marginBottom: 8 }} />
              <div style={{ fontWeight: 600, color: '#475569', fontSize: 14 }}>No active orders in the queue</div>
              <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                Orders placed via Store Kiosk or Agent Console will appear here.
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Sidebar Utilities */}
      <aside style={{
        borderLeft: '1px solid #e2e8f0',
        background: '#ffffff',
        padding: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
        overflowY: 'auto',
      }}>
        {/* Scanner Simulation */}
        <div style={{ 
          background: '#ffffff', 
          border: '1px solid #e2e8f0', 
          borderRadius: 8, 
          padding: 16, 
          boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
          display: 'flex', 
          flexDirection: 'column', 
          gap: 12 
        }}>
          <h3 style={{ 
            fontSize: 14, 
            fontWeight: 700, 
            margin: 0, 
            display: 'flex', 
            alignItems: 'center', 
            gap: 8,
            color: '#0c2340',
          }}>
            <Scan size={16} style={{ color: '#2563eb' }} /> Quick Barcode Scan
          </h3>
          <p style={{ fontSize: 12, color: '#64748b', margin: 0 }}>
            Enter a barcode or product name to fetch or edit inventory parameters.
          </p>

          <div style={{ display: 'flex', gap: 8 }}>
            <input 
              type="text" 
              placeholder="Barcode or name..." 
              value={searchBarcode}
              onChange={(e) => setSearchBarcode(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleBarcodeSearch()}
              style={{
                flex: 1,
                padding: '8px 12px',
                border: '1px solid #cbd5e1',
                borderRadius: 6,
                background: '#ffffff',
                color: '#0f172a',
                fontSize: 13,
                outline: 'none',
              }}
            />
            <button 
              onClick={handleBarcodeSearch}
              style={{
                background: '#2563eb',
                border: 'none',
                color: '#ffffff',
                padding: '8px 10px',
                borderRadius: 6,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <Search size={14} />
            </button>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>Presets:</span>
            {['Milk', 'Bread', 'Spinach'].map((name, i) => (
              <button 
                key={name}
                onClick={() => setSearchBarcode(['8901020304051', '8901020304052', '8901020304058'][i])} 
                style={{ 
                  fontSize: 11, 
                  background: '#f8fafc', 
                  border: '1px solid #e2e8f0', 
                  padding: '2px 6px', 
                  borderRadius: 4, 
                  cursor: 'pointer', 
                  color: '#475569',
                  fontWeight: 500,
                }}
              >
                {name}
              </button>
            ))}
          </div>

          {scanResult && (
            <div style={{
              background: '#f8fafc',
              padding: 12,
              borderRadius: 6,
              border: '1px solid #e2e8f0',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>{scanResult.name}</span>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#475569' }}>
                <span>Aisle: {scanResult.location}</span>
                <span>Price: ₹{scanResult.price}</span>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid #e2e8f0', paddingTop: 8, marginTop: 4 }}>
                <span style={{ fontSize: 12, color: '#475569' }}>Edit Stock:</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <input 
                    type="number" 
                    value={stockEditValue}
                    onChange={(e) => setStockEditValue(parseInt(e.target.value) || 0)}
                    style={{ 
                      width: 50, 
                      padding: 4, 
                      textAlign: 'center', 
                      border: '1px solid #cbd5e1', 
                      borderRadius: 4, 
                      background: '#ffffff', 
                      color: '#0f172a', 
                      fontSize: 13,
                      outline: 'none',
                    }}
                  />
                  <button 
                    onClick={handleUpdateStock}
                    style={{ 
                      background: '#059669', 
                      border: 'none', 
                      color: '#fff', 
                      padding: '4px 8px', 
                      borderRadius: 4, 
                      cursor: 'pointer', 
                      display: 'flex', 
                      alignItems: 'center' 
                    }}
                  >
                    <Check size={12} />
                  </button>
                </div>
              </div>

              {showStockCheckAlert && (
                <div style={{ fontSize: 12, color: '#059669', fontWeight: 600, textAlign: 'center' }}>
                  Stock updated successfully
                </div>
              )}
            </div>
          )}
        </div>

        {/* Stock Alerts */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          
          {/* Low Stock Panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h4 style={{ 
              fontSize: 13, 
              fontWeight: 700, 
              margin: 0, 
              color: '#dc2626', 
              display: 'flex', 
              alignItems: 'center', 
              gap: 6 
            }}>
              <AlertTriangle size={14} /> Low Stock ({lowStockItems.length})
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {lowStockItems.map(item => (
                <div key={item.id} style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center', 
                  padding: '8px 12px', 
                  background: '#fef2f2', 
                  border: '1px solid #fecaca', 
                  borderRadius: 6, 
                  fontSize: 12 
                }}>
                  <span style={{ fontWeight: 500, color: '#0f172a' }}>{item.name}</span>
                  <span style={{ fontWeight: 600, color: '#dc2626' }}>Qty: {item.stock}</span>
                </div>
              ))}
              {lowStockItems.length === 0 && (
                <div style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', padding: 12 }}>
                  All items well-stocked
                </div>
              )}
            </div>
          </div>

          {/* Expiring Soon Panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <h4 style={{ 
              fontSize: 13, 
              fontWeight: 700, 
              margin: 0, 
              color: '#b45309', 
              display: 'flex', 
              alignItems: 'center', 
              gap: 6 
            }}>
              <Hourglass size={14} /> Expiry Warnings ({expiringItems.length})
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {expiringItems.map(item => (
                <div key={item.id} style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center', 
                  padding: '8px 12px', 
                  background: '#fffbeb', 
                  border: '1px solid #fde68a', 
                  borderRadius: 6, 
                  fontSize: 12 
                }}>
                  <span style={{ fontWeight: 500, color: '#0f172a' }}>{item.name}</span>
                  <span style={{ fontWeight: 600, color: '#b45309' }}>Exp: {item.expiry}</span>
                </div>
              ))}
              {expiringItems.length === 0 && (
                <div style={{ fontSize: 12, color: '#94a3b8', textAlign: 'center', padding: 12 }}>
                  No items expiring soon
                </div>
              )}
            </div>
          </div>

        </div>
      </aside>
    </div>
  );
};
