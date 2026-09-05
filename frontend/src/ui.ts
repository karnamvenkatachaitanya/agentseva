// Clean, professional fintech light design tokens (Razorpay / Stripe inspired)
import type { CSSProperties } from 'react';

export const C = {
  bg: '#f8fafc',
  panel: '#ffffff',
  panel2: '#f1f5f9',
  border: '#e2e8f0',
  borderDark: '#cbd5e1',
  text: '#0f172a',
  sub: '#475569',
  muted: '#64748b',
  blue: '#2563eb',
  blueHover: '#1d4ed8',
  blueSoft: '#eff6ff',
  emerald: '#059669',
  amber: '#d97706',
  red: '#dc2626',
};

export const STATUS_THEME: Record<string, { bg: string; text: string; border: string }> = {
  paid: { bg: '#ecfdf5', text: '#059669', border: '#a7f3d0' },
  success: { bg: '#ecfdf5', text: '#059669', border: '#a7f3d0' },
  captured: { bg: '#ecfdf5', text: '#059669', border: '#a7f3d0' },
  completed: { bg: '#ecfdf5', text: '#059669', border: '#a7f3d0' },
  
  pending: { bg: '#fffbeb', text: '#b45309', border: '#fde68a' },
  initiated: { bg: '#fffbeb', text: '#b45309', border: '#fde68a' },
  preparing: { bg: '#eff6ff', text: '#2563eb', border: '#bfdbfe' },
  ready: { bg: '#f0fdf4', text: '#16a34a', border: '#bbf7d0' },
  
  failed: { bg: '#fef2f2', text: '#dc2626', border: '#fecaca' },
  error: { bg: '#fef2f2', text: '#dc2626', border: '#fecaca' },
  recovered: { bg: '#faf5ff', text: '#7c3aed', border: '#e9d5ff' },
  received: { bg: '#f0f9ff', text: '#0284c7', border: '#bae6fd' },
};

export function statusColor(s: string): string {
  return STATUS_THEME[s]?.text || '#475569';
}

export const CATEGORY_EMOJI: Record<string, string> = {
  Dairy: '🥛',
  'Dairy & Eggs': '🥛',
  Staples: '🌾',
  Oils: '🛢️',
  Snacks: '🍪',
  Beverages: '☕',
  Household: '🧼',
  Digital: '💻',
  Pantry: '🍯',
  Bakery: '🍞',
};

export function catEmoji(category: string): string {
  return CATEGORY_EMOJI[category] || '📦';
}

export const card: CSSProperties = {
  background: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: 10,
  padding: 16,
  boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.03)',
  transition: 'all 0.15s ease',
};

export const input: CSSProperties = {
  padding: '8px 12px',
  borderRadius: 6,
  border: '1px solid #cbd5e1',
  background: '#ffffff',
  color: '#0f172a',
  fontSize: 13,
  outline: 'none',
  fontFamily: 'inherit',
  boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.03)',
  transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
};

export const btn: CSSProperties = {
  padding: '8px 16px',
  borderRadius: 6,
  border: '1px solid #2563eb',
  background: '#2563eb',
  color: '#ffffff',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 600,
  fontFamily: 'inherit',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 6,
  boxShadow: '0 1px 2px 0 rgba(37, 99, 235, 0.2)',
  transition: 'all 0.15s ease',
};

export const ghostBtn: CSSProperties = {
  padding: '7px 12px',
  borderRadius: 6,
  border: '1px solid #e2e8f0',
  background: '#ffffff',
  color: '#334155',
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 500,
  fontFamily: 'inherit',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 5,
  boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.02)',
  transition: 'all 0.15s ease',
};

export function badge(colorOrStatus: string): CSSProperties {
  const theme = STATUS_THEME[colorOrStatus];
  if (theme) {
    return {
      background: theme.bg,
      color: theme.text,
      border: `1px solid ${theme.border}`,
      borderRadius: 4,
      padding: '2px 8px',
      fontSize: 11,
      textTransform: 'uppercase',
      fontWeight: 600,
      letterSpacing: '0.02em',
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
    };
  }
  return {
    background: '#f1f5f9',
    color: '#334155',
    border: '1px solid #e2e8f0',
    borderRadius: 4,
    padding: '2px 8px',
    fontSize: 11,
    textTransform: 'uppercase',
    fontWeight: 600,
    letterSpacing: '0.02em',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
  };
}

export function inr(n: number): string {
  return '₹' + Number(n).toLocaleString('en-IN');
}
