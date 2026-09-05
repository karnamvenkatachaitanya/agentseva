import { create } from 'zustand';

export interface Product {
  id: string;
  name: string;
  price: number;
  category: string;
  image: string;
  description: string;
  stock: number;
  expiry?: string;
  location: string;
  barcode: string;
}

export interface CartItem {
  product: Product;
  quantity: number;
}

export interface Order {
  id: string;
  items: CartItem[];
  total: number;
  type: 'self_pickup' | 'assisted' | 'service_boy' | 'home_delivery';
  status: 'pending' | 'preparing' | 'ready' | 'completed';
  customerName: string;
  phone: string;
  createdAt: string;
}

export interface VoiceMessage {
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
}

interface KioskState {
  // Navigation & Role
  activeRole: 'customer' | 'supervisor' | 'owner';
  setActiveRole: (role: 'customer' | 'supervisor' | 'owner') => void;

  // Accessibility Settings
  accessibility: {
    highContrast: boolean;
    largeFont: boolean;
    voiceFeedback: boolean;
    assistiveTouch: boolean;
  };
  toggleAccessibility: (key: 'highContrast' | 'largeFont' | 'voiceFeedback' | 'assistiveTouch') => void;

  // Catalog
  products: Product[];
  setProducts: (products: Product[]) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  selectedCategory: string;
  setSelectedCategory: (category: string) => void;

  // Cart
  cart: CartItem[];
  addToCart: (product: Product) => void;
  removeFromCart: (productId: string) => void;
  updateCartQuantity: (productId: string, quantity: number) => void;
  clearCart: () => void;

  // AI Voice Assistant Sim
  isVoiceListening: boolean;
  setIsVoiceListening: (listening: boolean) => void;
  voiceHistory: VoiceMessage[];
  addVoiceMessage: (sender: 'user' | 'assistant', text: string) => void;
  clearVoiceHistory: () => void;

  // AI Gesture Control Sim
  isGestureCameraActive: boolean;
  setIsGestureCameraActive: (active: boolean) => void;
  lastGesture: string;
  setLastGesture: (gesture: string) => void;

  // AI OCR Scanner Sim
  ocrFile: string | null;
  ocrProcessing: boolean;
  setOcrFile: (file: string | null) => void;
  setOcrProcessing: (processing: boolean) => void;

  // Supervisor Orders
  orders: Order[];
  addOrder: (order: Order) => void;
  updateOrderStatus: (orderId: string, status: Order['status']) => void;
}

import { kiranaProducts } from '../data/kiranaProducts';

const initialProducts: Product[] = kiranaProducts;

const initialOrders: Order[] = [
  {
    id: 'ORD-8942',
    items: [
      { product: initialProducts[0], quantity: 2 },
      { product: initialProducts[1], quantity: 1 }
    ],
    total: 230,
    type: 'self_pickup',
    status: 'pending',
    customerName: 'Aarav Sharma',
    phone: '9876543210',
    createdAt: '2026-06-04T10:15:00Z'
  },
  {
    id: 'ORD-7751',
    items: [
      { product: initialProducts[3], quantity: 1 },
      { product: initialProducts[4], quantity: 2 }
    ],
    total: 420,
    type: 'assisted',
    status: 'preparing',
    customerName: 'Priya Patel',
    phone: '9123456789',
    createdAt: '2026-06-04T10:02:00Z'
  }
];

export const useKioskStore = create<KioskState>((set) => ({
  activeRole: 'customer',
  setActiveRole: (role) => set({ activeRole: role }),

  accessibility: {
    highContrast: false,
    largeFont: false,
    voiceFeedback: false,
    assistiveTouch: false,
  },
  toggleAccessibility: (key) =>
    set((state) => ({
      accessibility: {
        ...state.accessibility,
        [key]: !state.accessibility[key],
      },
    })),

  products: initialProducts,
  setProducts: (products) => set({ products }),
  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),
  selectedCategory: 'All',
  setSelectedCategory: (category) => set({ selectedCategory: category }),

  cart: [],
  addToCart: (product) =>
    set((state) => {
      const existing = state.cart.find((item) => item.product.id === product.id);
      if (existing) {
        return {
          cart: state.cart.map((item) =>
            item.product.id === product.id
              ? { ...item, quantity: item.quantity + 1 }
              : item
          ),
        };
      }
      return { cart: [...state.cart, { product, quantity: 1 }] };
    }),
  removeFromCart: (productId) =>
    set((state) => ({
      cart: state.cart.filter((item) => item.product.id !== productId),
    })),
  updateCartQuantity: (productId, quantity) =>
    set((state) => {
      if (quantity <= 0) {
        return {
          cart: state.cart.filter((item) => item.product.id !== productId),
        };
      }
      return {
        cart: state.cart.map((item) =>
          item.product.id === productId ? { ...item, quantity } : item
        ),
      };
    }),
  clearCart: () => set({ cart: [] }),

  isVoiceListening: false,
  setIsVoiceListening: (listening) => set({ isVoiceListening: listening }),
  voiceHistory: [
    { sender: 'assistant', text: 'Namaste! How can I help you today? You can say "Add milk and bread", "Where is the honey?", or "Help me check out".', timestamp: '10:24' }
  ],
  addVoiceMessage: (sender, text) =>
    set((state) => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      return {
        voiceHistory: [...state.voiceHistory, { sender, text, timestamp: timeStr }],
      };
    }),
  clearVoiceHistory: () => set({ voiceHistory: [] }),

  isGestureCameraActive: false,
  setIsGestureCameraActive: (active) => set({ isGestureCameraActive: active }),
  lastGesture: 'None',
  setLastGesture: (gesture) => set({ lastGesture: gesture }),

  ocrFile: null,
  ocrProcessing: false,
  setOcrFile: (file) => set({ ocrFile: file }),
  setOcrProcessing: (processing) => set({ ocrProcessing: processing }),

  orders: initialOrders,
  addOrder: (order) => set((state) => ({ orders: [order, ...state.orders] })),
  updateOrderStatus: (orderId, status) =>
    set((state) => ({
      orders: state.orders.map((order) =>
        order.id === orderId ? { ...order, status } : order
      ),
    })),
}));
