// Typed API client for the AgentSeva backend. All calls go to the same-origin
// /api/v1 prefix (Vite dev proxy / nginx forwards to the FastAPI backend).

const BASE = '/api/v1';

export interface Product {
  id: number;
  name: string;
  description: string;
  price_inr: number;
  category: string;
  stock_quantity: number;
  image_url: string;
  in_stock: boolean;
  created_at: string | null;
}

export interface ProductInput {
  name: string;
  description: string;
  price_inr: number;
  category: string;
  stock_quantity: number;
  image_url: string;
}

export interface OrderLine {
  product_id: number;
  name: string;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface Order {
  id: number;
  customer_name: string;
  customer_phone: string;
  items: OrderLine[];
  total_amount: number;
  razorpay_order_id: string | null;
  razorpay_payment_id: string | null;
  razorpay_payment_link_id: string | null;
  payment_link: string | null;
  status: string;
  created_at: string | null;
}

export interface AuditTrace {
  id: number;
  trace_id: string;
  session_id: string;
  timestamp: string;
  user_intent: string;
  agent_reasoning: string;
  tool_called: string;
  payload_sent: unknown;
  api_response: unknown;
  status: string;
  latency_ms: number | null;
}

export async function readJsonResponse<T = unknown>(res: Response): Promise<T | null> {
  const text = await res.text();
  if (!text) return null;

  const contentType = res.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) {
    throw new Error(
      `The service returned an HTML page instead of JSON (HTTP ${res.status}). It may be offline or not published yet.`,
    );
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error(`The service returned invalid JSON (HTTP ${res.status}).`);
  }
}

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const data = await readJsonResponse<Record<string, unknown>>(res);
  if (!res.ok) {
    const detail = data && (data.detail || data.error) ? data.detail || data.error : res.statusText;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data as T;
}

export const api = {
  // Catalog
  listProducts: (query?: string, category?: string) => {
    const p = new URLSearchParams();
    if (query) p.set('query', query);
    if (category) p.set('category', category);
    const qs = p.toString();
    return req<Product[]>(`/products${qs ? '?' + qs : ''}`);
  },
  categories: () => req<string[]>('/products/categories'),
  createProduct: (body: ProductInput) => req<Product>('/products', { method: 'POST', body: JSON.stringify(body) }),
  updateProduct: (id: number, body: Partial<ProductInput>) =>
    req<Product>(`/products/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteProduct: (id: number) => req<{ deleted: number }>(`/products/${id}`, { method: 'DELETE' }),

  // Orders
  listOrders: () => req<Order[]>('/orders'),
  checkout: (body: { customer_name: string; customer_phone: string; items: { product_id: number; quantity: number }[] }) =>
    req<{ status: string; payment_link: string; total_inr: number; line_items: OrderLine[] }>(
      '/orders/checkout',
      { method: 'POST', body: JSON.stringify(body) },
    ),
  recover: (id: number) =>
    req<{ order: Order; recovery: Record<string, unknown> }>(`/orders/${id}/recover`, { method: 'POST' }),

  // Agent
  chat: (message: string, session_id: string) =>
    req<{ session_id: string; reply: string; requires_escalation: boolean; actions_taken: unknown[] }>(
      '/agent/chat',
      { method: 'POST', body: JSON.stringify({ message, session_id }) },
    ),

  // Audit & guardrails
  recentTraces: (limit = 60) => req<AuditTrace[]>(`/audit/recent?limit=${limit}`),
  limits: () => req<Record<string, number>>('/audit/limits'),
  metrics: () => req<Record<string, number>>('/metrics'),
  health: () => req<Record<string, unknown>>('/health'),
};
