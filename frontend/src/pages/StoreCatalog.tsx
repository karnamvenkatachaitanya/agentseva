import { useCallback, useEffect, useState } from 'react';
import { 
  Package, 
  Search, 
  Plus, 
  Edit3, 
  Trash2, 
  X, 
  Filter
} from 'lucide-react';
import { api, type Product, type ProductInput } from '../api';
import { catEmoji, inr } from '../ui';

const EMPTY: ProductInput = {
  name: '', 
  description: '', 
  price_inr: 0, 
  category: '', 
  stock_quantity: 0, 
  image_url: '',
};

export function StoreCatalog() {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<Product | null>(null);
  const [form, setForm] = useState<ProductInput>(EMPTY);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    try {
      setError('');
      const [p, c] = await Promise.all([
        api.listProducts(query || undefined, category || undefined),
        api.categories(),
      ]);
      setProducts(p);
      setCategories(c);
    } catch (e) {
      setError(String(e));
    }
  }, [query, category]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY);
    setShowForm(true);
  };

  const openEdit = (p: Product) => {
    setEditing(p);
    setForm({
      name: p.name, 
      description: p.description, 
      price_inr: p.price_inr,
      category: p.category, 
      stock_quantity: p.stock_quantity, 
      image_url: p.image_url,
    });
    setShowForm(true);
  };

  const save = async () => {
    try {
      setError('');
      if (editing) await api.updateProduct(editing.id, form);
      else await api.createProduct(form);
      setShowForm(false);
      await load();
    } catch (e) {
      setError(String(e));
    }
  };

  const remove = async (p: Product) => {
    if (!confirm(`Delete "${p.name}"?`)) return;
    try {
      await api.deleteProduct(p.id);
      await load();
    } catch (e) {
      setError(String(e));
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '9px 14px',
    borderRadius: 6,
    border: '1px solid #cbd5e1',
    background: '#ffffff',
    color: '#0f172a',
    fontSize: 13,
    outline: 'none',
    fontFamily: 'inherit',
  };

  return (
    <div style={{ padding: '24px 28px', height: '100%', overflowY: 'auto', background: '#f8fafc', color: '#0f172a' }}>
      {/* Header & Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 14 }}>
        <div>
          <h1 style={{ 
            fontFamily: 'Plus Jakarta Sans, sans-serif', 
            fontSize: 20, 
            fontWeight: 700, 
            margin: 0, 
            display: 'flex', 
            alignItems: 'center', 
            gap: 8,
            color: '#0c2340',
          }}>
            <Package size={20} style={{ color: '#2563eb' }} />
            Kirana Inventory Catalog
          </h1>
          <p style={{ color: '#64748b', fontSize: 13, marginTop: 4 }}>
            Manage store items, pricing, categories, and stock quantities for autonomous agent checkout.
          </p>
        </div>

        <button 
          onClick={openCreate}
          style={{
            background: '#2563eb',
            color: '#fff',
            border: 'none',
            padding: '8px 16px',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            boxShadow: '0 1px 3px rgba(37, 99, 235, 0.3)',
          }}
        >
          <Plus size={15} />
          <span>Add Product</span>
        </button>
      </div>

      {/* Filter Row */}
      <div style={{ 
        display: 'flex', 
        gap: 12, 
        alignItems: 'center', 
        marginBottom: 20, 
        flexWrap: 'wrap',
        background: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: 8,
        padding: 12,
        boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
      }}>
        <div style={{ position: 'relative', flex: '1 1 240px' }}>
          <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
          <input 
            style={{
              width: '100%',
              padding: '9px 14px 9px 36px',
              borderRadius: 6,
              border: '1px solid #cbd5e1',
              background: '#ffffff',
              color: '#0f172a',
              fontSize: 13,
              outline: 'none',
              fontFamily: 'inherit',
            }} 
            placeholder="Search items by name or description…" 
            value={query}
            onChange={(e) => setQuery(e.target.value)} 
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Filter size={14} style={{ color: '#64748b' }} />
          <select 
            style={{
              padding: '9px 14px',
              borderRadius: 6,
              border: '1px solid #cbd5e1',
              background: '#ffffff',
              color: '#0f172a',
              fontSize: 13,
              outline: 'none',
              fontFamily: 'inherit',
              cursor: 'pointer',
            }} 
            value={category} 
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All Categories ({products.length})</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
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

      {/* Products Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
        {products.map((p) => (
          <div 
            key={p.id} 
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              padding: 16,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
              transition: 'all 0.15s ease',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 28 }}>{catEmoji(p.category)}</span>
                <span style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: 4,
                  background: p.stock_quantity > 0 ? '#ecfdf5' : '#fef2f2',
                  color: p.stock_quantity > 0 ? '#059669' : '#dc2626',
                  border: `1px solid ${p.stock_quantity > 0 ? '#a7f3d0' : '#fecaca'}`,
                }}>
                  {p.stock_quantity > 0 ? `${p.stock_quantity} in stock` : 'out of stock'}
                </span>
              </div>

              <div style={{ fontWeight: 600, fontSize: 14, marginTop: 10, color: '#0f172a' }}>
                {p.name}
              </div>

              <div style={{ color: '#64748b', fontSize: 12, marginTop: 4, minHeight: 34, lineHeight: 1.4 }}>
                {p.description || 'Kirana store essential goods.'}
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, paddingTop: 10, borderTop: '1px solid #f1f5f9' }}>
                <div>
                  <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 600 }}>PRICE</div>
                  <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'Plus Jakarta Sans, sans-serif', color: '#0f172a' }}>
                    {inr(p.price_inr)}
                  </div>
                </div>
                <div style={{ 
                  fontSize: 11, 
                  color: '#475569', 
                  background: '#f1f5f9', 
                  padding: '3px 8px', 
                  borderRadius: 4,
                  fontWeight: 500,
                }}>
                  {p.category}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                <button 
                  onClick={() => openEdit(p)}
                  style={{
                    flex: 1,
                    padding: '6px 10px',
                    borderRadius: 6,
                    border: '1px solid #e2e8f0',
                    background: '#ffffff',
                    color: '#334155',
                    fontSize: 12,
                    fontWeight: 500,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 5,
                  }}
                >
                  <Edit3 size={12} />
                  <span>Edit</span>
                </button>
                <button 
                  onClick={() => remove(p)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 6,
                    border: '1px solid #fecaca',
                    background: '#fef2f2',
                    color: '#dc2626',
                    fontSize: 12,
                    fontWeight: 500,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Add / Edit Product Modal */}
      {showForm && (
        <div 
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.5)',
            backdropFilter: 'blur(4px)',
            WebkitBackdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 999,
          }}
          onClick={() => setShowForm(false)}
        >
          <div 
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: 10,
              padding: 24,
              width: 440,
              maxWidth: '92vw',
              boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: '#0c2340', fontFamily: 'Plus Jakarta Sans, sans-serif' }}>
                {editing ? 'Edit Product' : 'Add New Product'}
              </h2>
              <button 
                onClick={() => setShowForm(false)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: '0.02em', display: 'block', marginBottom: 4 }}>
                  PRODUCT NAME
                </label>
                <input 
                  style={inputStyle} 
                  placeholder="e.g. Fortune Sunflower Oil 1L" 
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })} 
                />
              </div>

              <div>
                <label style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: '0.02em', display: 'block', marginBottom: 4 }}>
                  DESCRIPTION
                </label>
                <input 
                  style={inputStyle} 
                  placeholder="e.g. Refined edible oil, rich in Vitamin E" 
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })} 
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: '0.02em', display: 'block', marginBottom: 4 }}>
                    PRICE (₹ INR)
                  </label>
                  <input 
                    style={inputStyle} 
                    type="number" 
                    placeholder="150" 
                    value={form.price_inr || ''}
                    onChange={(e) => setForm({ ...form, price_inr: Number(e.target.value) })} 
                  />
                </div>

                <div>
                  <label style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: '0.02em', display: 'block', marginBottom: 4 }}>
                    STOCK QTY
                  </label>
                  <input 
                    style={inputStyle} 
                    type="number" 
                    placeholder="50" 
                    value={form.stock_quantity || ''}
                    onChange={(e) => setForm({ ...form, stock_quantity: Number(e.target.value) })} 
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: 11, color: '#64748b', fontWeight: 600, letterSpacing: '0.02em', display: 'block', marginBottom: 4 }}>
                  CATEGORY
                </label>
                <input 
                  style={inputStyle} 
                  placeholder="e.g. Oils, Staples, Dairy, Snacks" 
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })} 
                />
              </div>

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 12 }}>
                <button 
                  onClick={() => setShowForm(false)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: 6,
                    border: '1px solid #e2e8f0',
                    background: '#ffffff',
                    color: '#475569',
                    cursor: 'pointer',
                    fontSize: 13,
                    fontWeight: 500,
                  }}
                >
                  Cancel
                </button>
                <button 
                  onClick={save}
                  disabled={!form.name || form.price_inr <= 0}
                  style={{
                    padding: '8px 20px',
                    borderRadius: 6,
                    border: 'none',
                    background: form.name && form.price_inr > 0 ? '#2563eb' : '#94a3b8',
                    color: '#ffffff',
                    cursor: form.name && form.price_inr > 0 ? 'pointer' : 'not-allowed',
                    fontSize: 13,
                    fontWeight: 600,
                    boxShadow: form.name && form.price_inr > 0 ? '0 1px 3px rgba(37, 99, 235, 0.3)' : 'none',
                  }}
                >
                  Save Product
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
