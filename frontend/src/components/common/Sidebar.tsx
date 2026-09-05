import React, { useState } from 'react';
import { useKioskStore } from '../../stores/kioskStore';
import { 
  ShieldAlert, 
  TrendingUp, 
  Eye, 
  Type, 
  Volume2, 
  VolumeX, 
  Sparkles,
  Smartphone,
  Accessibility,
  WifiOff
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { 
    activeRole, 
    setActiveRole, 
    accessibility, 
    toggleAccessibility 
  } = useKioskStore();

  const [showAccessModal, setShowAccessModal] = useState(false);

  return (
    <>
      {/* 1. DESKTOP SIDEBAR: visible on screens > 768px */}
      <aside className="desktop-nav glass-panel" style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: '24px',
        borderRadius: '0px',
        borderRight: '1px solid var(--border-glass)',
        justifyContent: 'space-between',
        width: '300px',
        flexShrink: 0
      }}>
        <div>
          {/* Branding */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '32px' }}>
            <div style={{
              background: 'var(--accent-gradient)',
              color: '#fff',
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: 'var(--shadow-glow)'
            }}>
              <Sparkles size={20} />
            </div>
            <div>
              <h2 style={{ fontFamily: 'var(--font-heading)', fontWeight: 800, fontSize: '1.25rem', margin: 0, background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Agent Seva
              </h2>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                Offline Web & Mobile
              </span>
            </div>
          </div>

          {/* Local SQLite / Offline status tag */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid rgba(245, 158, 11, 0.2)',
            padding: '8px 12px',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '32px',
            color: 'var(--warning)'
          }}>
            <WifiOff size={16} className="sync-pulse" />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 800 }}>Standalone Mode</span>
              <span style={{ fontSize: '0.6rem', color: 'var(--text-secondary)' }}>SQLite Local DB Active</span>
            </div>
          </div>

          {/* Roles Selector */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.5px' }}>
              Choose Module View
            </span>
            
            <button 
              onClick={() => setActiveRole('customer')}
              className={activeRole === 'customer' ? 'btn-primary' : 'btn-secondary'}
              style={{ width: '100%', justifyContent: 'flex-start', gap: '12px', padding: '12px 16px' }}
            >
              <Smartphone size={18} />
              <span>Customer Shop</span>
            </button>

            <button 
              onClick={() => setActiveRole('supervisor')}
              className={activeRole === 'supervisor' ? 'btn-primary' : 'btn-secondary'}
              style={{ width: '100%', justifyContent: 'flex-start', gap: '12px', padding: '12px 16px' }}
            >
              <ShieldAlert size={18} />
              <span>Supervisor Queue</span>
            </button>

            <button 
              onClick={() => setActiveRole('owner')}
              className={activeRole === 'owner' ? 'btn-primary' : 'btn-secondary'}
              style={{ width: '100%', justifyContent: 'flex-start', gap: '12px', padding: '12px 16px' }}
            >
              <TrendingUp size={18} />
              <span>Owner Panel</span>
            </button>
          </div>
        </div>

        {/* Accessibility Menu */}
        <div style={{
          background: 'rgba(79, 70, 229, 0.04)',
          border: '1px solid var(--border-glass)',
          borderRadius: 'var(--radius-md)',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <Accessibility size={16} style={{ color: 'var(--accent-primary)' }} />
            <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>Accessibility Settings</span>
          </div>

          <button 
            onClick={() => toggleAccessibility('highContrast')}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: accessibility.highContrast ? 'var(--accent-primary)' : 'transparent',
              color: accessibility.highContrast ? '#fff' : 'var(--text-primary)',
              border: '1px solid var(--border-glass)',
              padding: '6px 10px',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '0.8rem',
              width: '100%'
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Eye size={14} /> High Contrast
            </span>
            <span style={{ fontSize: '0.65rem', fontWeight: 'bold' }}>{accessibility.highContrast ? 'ON' : 'OFF'}</span>
          </button>

          <button 
            onClick={() => toggleAccessibility('largeFont')}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: accessibility.largeFont ? 'var(--accent-primary)' : 'transparent',
              color: accessibility.largeFont ? '#fff' : 'var(--text-primary)',
              border: '1px solid var(--border-glass)',
              padding: '6px 10px',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '0.8rem',
              width: '100%'
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Type size={14} /> Large Text
            </span>
            <span style={{ fontSize: '0.65rem', fontWeight: 'bold' }}>{accessibility.largeFont ? 'ON' : 'OFF'}</span>
          </button>

          <button 
            onClick={() => toggleAccessibility('voiceFeedback')}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: accessibility.voiceFeedback ? 'var(--accent-primary)' : 'transparent',
              color: accessibility.voiceFeedback ? '#fff' : 'var(--text-primary)',
              border: '1px solid var(--border-glass)',
              padding: '6px 10px',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '0.8rem',
              width: '100%'
            }}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {accessibility.voiceFeedback ? <Volume2 size={14} /> : <VolumeX size={14} />}
              Voice Assist
            </span>
            <span style={{ fontSize: '0.65rem', fontWeight: 'bold' }}>{accessibility.voiceFeedback ? 'ON' : 'OFF'}</span>
          </button>
        </div>
      </aside>

      {/* 2. MOBILE BOTTOM NAVIGATION: visible on screens <= 768px */}
      <nav className="mobile-nav glass-panel" style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: '64px',
        display: 'none',
        gridTemplateColumns: 'repeat(4, 1fr)',
        alignItems: 'center',
        justifyItems: 'center',
        zIndex: 1000,
        borderRadius: '0px',
        borderTop: '1px solid var(--border-glass)',
        borderLeft: 'none',
        borderRight: 'none',
        borderBottom: 'none',
        background: 'var(--bg-secondary)',
        padding: '0 8px'
      }}>
        <button 
          onClick={() => setActiveRole('customer')}
          style={{
            background: 'transparent',
            border: 'none',
            color: activeRole === 'customer' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.7rem',
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          <Smartphone size={20} />
          Shop
        </button>

        <button 
          onClick={() => setActiveRole('supervisor')}
          style={{
            background: 'transparent',
            border: 'none',
            color: activeRole === 'supervisor' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.7rem',
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          <ShieldAlert size={20} />
          Queue
        </button>

        <button 
          onClick={() => setActiveRole('owner')}
          style={{
            background: 'transparent',
            border: 'none',
            color: activeRole === 'owner' ? 'var(--accent-primary)' : 'var(--text-secondary)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.7rem',
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          <TrendingUp size={20} />
          Insights
        </button>

        <button 
          onClick={() => setShowAccessModal(true)}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-secondary)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.7rem',
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          <Accessibility size={20} style={{ color: 'var(--accent-primary)' }} />
          Options
        </button>
      </nav>

      {/* CSS Helper stylesheet inject for hiding/showing desktop/mobile bars */}
      <style>{`
        @media (max-width: 768px) {
          .desktop-nav {
            display: none !important;
          }
          .mobile-nav {
            display: grid !important;
          }
        }
      `}</style>

      {/* Mobile Accessibility Sheet Popup */}
      {showAccessModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'flex-end',
          zIndex: 1100
        }}>
          <div style={{
            background: 'var(--bg-secondary)',
            width: '100%',
            borderTopLeftRadius: 'var(--radius-lg)',
            borderTopRightRadius: 'var(--radius-lg)',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 800, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Accessibility size={18} /> Accessibility Settings
              </span>
              <button 
                onClick={() => setShowAccessModal(false)}
                style={{ background: 'transparent', border: 'none', fontSize: '1.2rem', fontWeight: 'bold', color: 'var(--text-primary)' }}
              >
                &times;
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <button 
                onClick={() => toggleAccessibility('highContrast')}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: accessibility.highContrast ? 'var(--accent-primary)' : 'var(--bg-primary)',
                  color: accessibility.highContrast ? '#fff' : 'var(--text-primary)',
                  border: '1px solid var(--border-glass)',
                  padding: '12px',
                  borderRadius: 'var(--radius-md)',
                  fontWeight: 600,
                  fontSize: '0.85rem'
                }}
              >
                <span>High Contrast</span>
                <span>{accessibility.highContrast ? 'ACTIVE' : 'INACTIVE'}</span>
              </button>

              <button 
                onClick={() => toggleAccessibility('largeFont')}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: accessibility.largeFont ? 'var(--accent-primary)' : 'var(--bg-primary)',
                  color: accessibility.largeFont ? '#fff' : 'var(--text-primary)',
                  border: '1px solid var(--border-glass)',
                  padding: '12px',
                  borderRadius: 'var(--radius-md)',
                  fontWeight: 600,
                  fontSize: '0.85rem'
                }}
              >
                <span>Large Fonts</span>
                <span>{accessibility.largeFont ? 'ACTIVE' : 'INACTIVE'}</span>
              </button>

              <button 
                onClick={() => toggleAccessibility('voiceFeedback')}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: accessibility.voiceFeedback ? 'var(--accent-primary)' : 'var(--bg-primary)',
                  color: accessibility.voiceFeedback ? '#fff' : 'var(--text-primary)',
                  border: '1px solid var(--border-glass)',
                  padding: '12px',
                  borderRadius: 'var(--radius-md)',
                  fontWeight: 600,
                  fontSize: '0.85rem'
                }}
              >
                <span>Voice Synthesizer Feedback</span>
                <span>{accessibility.voiceFeedback ? 'ACTIVE' : 'INACTIVE'}</span>
              </button>
            </div>

            <button 
              className="btn-primary" 
              onClick={() => setShowAccessModal(false)}
              style={{ justifyContent: 'center', marginTop: '8px' }}
            >
              Done
            </button>
          </div>
        </div>
      )}
    </>
  );
};
