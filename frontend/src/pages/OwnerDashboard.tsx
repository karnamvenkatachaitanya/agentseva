import React, { useState } from 'react';
import type { Product } from '../stores/kioskStore';
import { useKioskStore } from '../stores/kioskStore';
import { 
  TrendingUp, 
  ShoppingBag, 
  Users, 
  Database,
  Plus, 
  Trash2, 
  DollarSign,
  UserPlus,
  Edit,
  Check,
  X,
  Scan,
  Camera,
  Loader2
} from 'lucide-react';

const scanPresets = [
  {
    name: 'A2 Grass-fed Cow Ghee (500ml)',
    price: 650,
    category: 'Dairy & Eggs',
    stock: 25,
    location: 'Aisle 3A (Refrigerated)',
    barcode: '8901020304060',
    description: 'Pure Desi A2 Cow Ghee, hand-churned using traditional Bilona method.',
    imageUrl: 'https://images.unsplash.com/photo-1589985270826-4b7bb135bc9d?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3'
  },
  {
    name: 'Organic Wildflower Honey (250g)',
    price: 240,
    category: 'Pantry',
    stock: 40,
    location: 'Aisle 2B (Spreads)',
    barcode: '8901020304061',
    description: 'Raw, unpasteurized forest wildflower honey with natural enzymes.',
    imageUrl: 'https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3'
  },
  {
    name: 'Premium Himalayan Pink Salt (500g)',
    price: 95,
    category: 'Pantry',
    stock: 50,
    location: 'Aisle 2A (Spices)',
    barcode: '8901020304062',
    description: 'Pure, mineral-rich pink salt sourced directly from the Himalayas.',
    imageUrl: 'https://images.unsplash.com/photo-1626132647523-66f5bf380027?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3'
  },
  {
    name: 'Gluten-Free Rolled Oats (1kg)',
    price: 320,
    category: 'Bakery',
    stock: 15,
    location: 'Aisle 1B (Cereals)',
    barcode: '8901020304063',
    description: '100% whole grain gluten-free rolled oats, high in soluble fiber.',
    imageUrl: 'https://images.unsplash.com/photo-1586444248902-2f64eddc13df?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3'
  }
];

export const OwnerDashboard: React.FC = () => {
  const { products, setProducts, orders } = useKioskStore();
  const [selectedCatFilter, setSelectedCatFilter] = useState('All');
  
  // New product form states
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newPrice, setNewPrice] = useState<number>(0);
  const [newCategory, setNewCategory] = useState('Dairy & Eggs');
  const [newStock, setNewStock] = useState<number>(0);
  const [newLocation, setNewLocation] = useState('');
  const [newBarcode, setNewBarcode] = useState('');
  const [newImage, setNewImage] = useState('');

  // Inline edit states
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editPrice, setEditPrice] = useState<number>(0);
  const [editCategory, setEditCategory] = useState('');
  const [editStock, setEditStock] = useState<number>(0);
  const [editLocation, setEditLocation] = useState('');
  const [editBarcode, setEditBarcode] = useState('');

  // Scan simulation states
  const [showScanModal, setShowScanModal] = useState(false);
  const [selectedPresetIndex, setSelectedPresetIndex] = useState(0);
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [scanLogs, setScanLogs] = useState<string[]>([]);
  const [scannedData, setScannedData] = useState<any>(null);

  // Staff roster states
  const [staffList, setStaffList] = useState([
    { id: 'S1', name: 'Rohan Deshmukh', role: 'Store Supervisor', status: 'Checked In', time: '08:00 AM' },
    { id: 'S2', name: 'Anjali Sharma', role: 'Support Assistant', status: 'Checked In', time: '09:15 AM' },
    { id: 'S3', name: 'Vikram Singh', role: 'Delivery Associate', status: 'On Field', time: '10:00 AM' },
    { id: 'S4', name: 'Deepa Roy', role: 'Billing Operator', status: 'Checked Out', time: 'Yesterday' }
  ]);
  const [newStaffName, setNewStaffName] = useState('');
  const [newStaffRole, setNewStaffRole] = useState('Support Assistant');

  // Business Analytics metrics
  const totalSales = orders.reduce((sum, order) => sum + order.total, 0) + 12500; // Add baseline mock sales
  const totalOrders = orders.length + 42;
  const averageCartValue = totalOrders > 0 ? Math.round(totalSales / totalOrders) : 0;
  const categoriesList = ['All', ...Array.from(new Set(products.map((p) => p.category)))];

  // Handler to add product
  const handleAddProduct = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName) return;
    
    const newProduct: Product = {
      id: `${products.length + 1}`,
      name: newName,
      price: newPrice,
      category: newCategory,
      image: newImage || 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3', // Grocery store placeholder
      description: 'Newly added store product.',
      stock: newStock,
      location: newLocation || 'Aisle 1',
      barcode: newBarcode || `89010203040${Math.floor(10 + Math.random() * 89)}`
    };

    setProducts([...products, newProduct]);
    
    // Clear form
    setNewName('');
    setNewPrice(0);
    setNewStock(0);
    setNewLocation('');
    setNewBarcode('');
    setNewImage('');
    setShowAddForm(false);
  };

  // Delete product
  const handleDeleteProduct = (id: string) => {
    setProducts(products.filter(p => p.id !== id));
  };

  // Add staff member
  const handleAddStaff = () => {
    if (!newStaffName) return;
    const newStaff = {
      id: `S${staffList.length + 1}`,
      name: newStaffName,
      role: newStaffRole,
      status: 'Checked In',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setStaffList([...staffList, newStaff]);
    setNewStaffName('');
  };

  // Inline edit handlers
  const startEditProduct = (p: Product) => {
    setEditingId(p.id);
    setEditName(p.name);
    setEditPrice(p.price);
    setEditCategory(p.category);
    setEditStock(p.stock);
    setEditLocation(p.location);
    setEditBarcode(p.barcode);
  };

  const handleSaveEdit = (id: string) => {
    const updated = products.map(p => 
      p.id === id 
        ? { 
            ...p, 
            name: editName, 
            price: editPrice, 
            category: editCategory, 
            stock: editStock, 
            location: editLocation,
            barcode: editBarcode
          } 
        : p
    );
    setProducts(updated);
    setEditingId(null);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
  };

  // Scanning simulation handler
  const handleStartScan = () => {
    setIsScanning(true);
    setScanProgress(0);
    setScanLogs([]);
    setScannedData(null);

    const logMessages = [
      'Initializing Camera feed overlay...',
      'Locating barcode region via YOLOv8 engine...',
      'Decoding barcode EAN-13 structure...',
      'Running PaddleOCR label segmentations...',
      'Extracting product text details & weights...',
      'Verifying nutritional values...',
      'Completed OCR & Barcode extraction successfully!'
    ];

    let currentStep = 0;
    const interval = setInterval(() => {
      if (currentStep < logMessages.length) {
        setScanLogs(prev => [...prev, `[System] ${logMessages[currentStep]}`]);
        setScanProgress(Math.floor(((currentStep + 1) / logMessages.length) * 100));
        currentStep++;
      } else {
        clearInterval(interval);
        setIsScanning(false);
        setScannedData(scanPresets[selectedPresetIndex]);
        setScanLogs(prev => [...prev, `[Success] All fields ready to apply!`]);
      }
    }, 600);
  };

  const handleApplyScannedData = () => {
    if (!scannedData) return;
    setNewName(scannedData.name);
    setNewPrice(scannedData.price);
    setNewCategory(scannedData.category);
    setNewStock(scannedData.stock);
    setNewLocation(scannedData.location);
    setNewBarcode(scannedData.barcode);
    setNewImage(scannedData.imageUrl);
    setShowAddForm(true);
    setShowScanModal(false);
  };

  const tableInputStyle = {
    width: '100%',
    padding: '6px 10px',
    border: '1px solid #e2e8f0',
    borderRadius: 'var(--radius-sm)',
    background: 'var(--bg-secondary)',
    color: 'var(--text-primary)',
    fontSize: '0.8rem',
    outline: 'none'
  };

  // Filtered products list for table
  const filteredTableProducts = products.filter(p => 
    selectedCatFilter === 'All' || p.category === selectedCatFilter
  );

  return (
    <div style={{ padding: '24px', overflowY: 'auto', height: '100vh', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h1 style={{ fontSize: '2rem', margin: 0, fontFamily: 'var(--font-heading)', fontWeight: 800 }}>
          Owner Control & Analytics
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          Evaluate store performance, audit inventory logs, and coordinate staff rosters.
        </p>
      </div>

      {/* KPI Cards Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '20px' }}>
        <div  style={{ padding: '20px', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#059669', padding: '12px', borderRadius: '12px' }}>
            <DollarSign size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Total Sales Today</span>
            <h3 style={{ fontSize: '1.5rem', fontWeight: 800, margin: '4px 0 0 0' }}>₹{totalSales.toLocaleString()}</h3>
          </div>
        </div>

        <div  style={{ padding: '20px', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#0c2340', padding: '12px', borderRadius: '12px' }}>
            <ShoppingBag size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Orders Handled</span>
            <h3 style={{ fontSize: '1.5rem', fontWeight: 800, margin: '4px 0 0 0' }}>{totalOrders}</h3>
          </div>
        </div>

        <div  style={{ padding: '20px', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(14, 165, 233, 0.15)', color: '#0284c7', padding: '12px', borderRadius: '12px' }}>
            <TrendingUp size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Average Basket Size</span>
            <h3 style={{ fontSize: '1.5rem', fontWeight: 800, margin: '4px 0 0 0' }}>₹{averageCartValue}</h3>
          </div>
        </div>

        <div  style={{ padding: '20px', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(139, 92, 246, 0.15)', color: 'var(--accent-secondary)', padding: '12px', borderRadius: '12px' }}>
            <Users size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Staff Checked In</span>
            <h3 style={{ fontSize: '1.5rem', fontWeight: 800, margin: '4px 0 0 0' }}>{staffList.filter(s => s.status !== 'Checked Out').length}</h3>
          </div>
        </div>
      </div>

      {/* Main Double Grid Section: Chart & Staff */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
        
        {/* Sales Chart Panel */}
        <div  style={{ padding: '20px', borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0 }}>📊 Sales Hourly Performance Trend</h3>
          
          {/* Custom SVG Chart */}
          <div style={{ width: '100%', height: '220px', display: 'flex', alignItems: 'flex-end', padding: '10px 0' }}>
            <svg style={{ width: '100%', height: '100%' }}>
              <defs>
                <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0c2340" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#0c2340" stopOpacity="0" />
                </linearGradient>
              </defs>

              {/* Grid Lines */}
              <line x1="5%" y1="20%" x2="95%" y2="20%" stroke="#e2e8f0" strokeWidth="1" strokeDasharray="4 4" />
              <line x1="5%" y1="50%" x2="95%" y2="50%" stroke="#e2e8f0" strokeWidth="1" strokeDasharray="4 4" />
              <line x1="5%" y1="80%" x2="95%" y2="80%" stroke="#e2e8f0" strokeWidth="1" />

              {/* Chart Line Path */}
              <path 
                d="M 50 180 Q 150 120 250 140 T 450 70 T 650 90 T 850 40 L 850 180 L 50 180 Z" 
                fill="url(#chartGrad)" 
              />
              <path 
                d="M 50 180 Q 150 120 250 140 T 450 70 T 650 90 T 850 40" 
                fill="none" 
                stroke="#0c2340" 
                strokeWidth="3.5" 
                strokeLinecap="round" 
              />

              {/* Data points */}
              <circle cx="50" cy="180" r="5" fill="#0c2340" stroke="#fff" strokeWidth="1.5" />
              <circle cx="205" cy="130" r="5" fill="#0c2340" stroke="#fff" strokeWidth="1.5" />
              <circle cx="360" cy="115" r="5" fill="#0c2340" stroke="#fff" strokeWidth="1.5" />
              <circle cx="510" cy="70" r="5" fill="#0c2340" stroke="#fff" strokeWidth="1.5" />
              <circle cx="660" cy="90" r="5" fill="#0c2340" stroke="#fff" strokeWidth="1.5" />
              <circle cx="810" cy="40" r="5" fill="#0c2340" stroke="#fff" strokeWidth="1.5" />

              {/* Labels */}
              <text x="50" y="198" fill="var(--text-secondary)" fontSize="10" textAnchor="middle">08:00</text>
              <text x="205" y="198" fill="var(--text-secondary)" fontSize="10" textAnchor="middle">10:00</text>
              <text x="360" y="198" fill="var(--text-secondary)" fontSize="10" textAnchor="middle">12:00</text>
              <text x="510" y="198" fill="var(--text-secondary)" fontSize="10" textAnchor="middle">14:00</text>
              <text x="660" y="198" fill="var(--text-secondary)" fontSize="10" textAnchor="middle">16:00</text>
              <text x="810" y="198" fill="var(--text-secondary)" fontSize="10" textAnchor="middle">18:00</text>
            </svg>
          </div>
        </div>

        {/* Staff Roster Panel */}
        <div  style={{ padding: '20px', borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Users size={20} style={{ color: 'var(--accent-secondary)' }} /> Staff Duty Roster
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', overflowY: 'auto', maxHeight: '180px' }}>
            {staffList.map(staff => (
              <div key={staff.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-primary)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700 }}>{staff.name}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{staff.role}</span>
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                  <span style={{ 
                    fontSize: '0.65rem', 
                    fontWeight: 'bold', 
                    color: staff.status === 'Checked Out' ? '#dc2626' : '#059669' 
                  }}>
                    {staff.status}
                  </span>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{staff.time}</span>
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderTop: '1px solid #e2e8f0', paddingTop: '10px' }}>
            <input 
              type="text" 
              placeholder="Name..." 
              value={newStaffName}
              onChange={(e) => setNewStaffName(e.target.value)}
              style={{ padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
            />
            <select
              value={newStaffRole}
              onChange={(e) => setNewStaffRole(e.target.value)}
              style={{ padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
            >
              <option value="Store Supervisor">Store Supervisor</option>
              <option value="Support Assistant">Support Assistant</option>
              <option value="Delivery Associate">Delivery Associate</option>
            </select>
            <button 
              onClick={handleAddStaff}
              className="btn-primary"
              style={{ width: '100%', justifyContent: 'center', padding: '8px', fontSize: '0.8rem', gap: '6px' }}
            >
              <UserPlus size={14} /> Add Staff
            </button>
          </div>
        </div>
      </div>

      {/* Inventory Management Section */}
      <div  style={{ padding: '20px', borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Database size={20} style={{ color: '#0c2340' }} /> Inventory Logs & Controls
          </h3>
          
          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              onClick={() => setShowScanModal(true)}
              className="btn-secondary"
              style={{ padding: '8px 16px', fontSize: '0.85rem', gap: '6px' }}
            >
              <Scan size={16} style={{ color: '#0c2340' }} /> Scan via Camera
            </button>
            <button 
              onClick={() => setShowAddForm(!showAddForm)}
              className="btn-primary"
              style={{ padding: '8px 16px', fontSize: '0.85rem', gap: '6px' }}
            >
              <Plus size={16} /> New Product
            </button>
          </div>
        </div>

        {/* Add Product Form */}
        {showAddForm && (
          <form onSubmit={handleAddProduct} style={{
            background: 'var(--bg-primary)',
            padding: '16px',
            borderRadius: 'var(--radius-sm)',
            border: '1.5px solid #e2e8f0',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '12px',
            alignItems: 'end'
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700 }}>Barcode</label>
              <input type="text" value={newBarcode} placeholder="Autogenerated if blank" onChange={e => setNewBarcode(e.target.value)} style={{ padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '0.8rem' }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700 }}>Product Name</label>
              <input type="text" value={newName} onChange={e => setNewName(e.target.value)} required style={{ padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '0.8rem' }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700 }}>Price (₹)</label>
              <input type="number" value={newPrice} onChange={e => setNewPrice(parseFloat(e.target.value) || 0)} required style={{ padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '0.8rem' }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700 }}>Category</label>
              <select value={newCategory} onChange={e => setNewCategory(e.target.value)} style={{ padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '0.8rem' }}>
                <option value="Fruits & Vegetables">Fruits & Vegetables</option>
                <option value="Bakery">Bakery</option>
                <option value="Dairy & Eggs">Dairy & Eggs</option>
                <option value="Pantry">Pantry</option>
              </select>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700 }}>Stock Qty</label>
              <input type="number" value={newStock} onChange={e => setNewStock(parseInt(e.target.value) || 0)} required style={{ padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '0.8rem' }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700 }}>Store Location</label>
              <input type="text" placeholder="e.g. Aisle 2A" value={newLocation} onChange={e => setNewLocation(e.target.value)} style={{ padding: '8px', border: '1px solid #e2e8f0', borderRadius: '4px', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '0.8rem' }} />
            </div>

            <div style={{ display: 'flex', gap: '6px' }}>
              <button type="submit" className="btn-primary" style={{ padding: '8px', fontSize: '0.8rem', width: '100%', justifyContent: 'center' }}>Save Product</button>
              <button type="button" onClick={() => {
                setShowAddForm(false);
                setNewBarcode('');
                setNewName('');
                setNewPrice(0);
                setNewStock(0);
                setNewLocation('');
              }} className="btn-secondary" style={{ padding: '8px', fontSize: '0.8rem', width: '100%', justifyContent: 'center' }}>Cancel</button>
            </div>
          </form>
        )}

        {/* Category Filters */}
        <div style={{ display: 'flex', gap: '8px', overflowX: 'auto' }}>
          {categoriesList.map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCatFilter(cat)}
              className={selectedCatFilter === cat ? 'btn-primary' : 'btn-secondary'}
              style={{ padding: '6px 12px', borderRadius: 'var(--radius-full)', fontSize: '0.8rem' }}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Inventory Registry Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '0.85rem',
            textAlign: 'left'
          }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                <th style={{ padding: '12px 8px', fontWeight: 700 }}>Barcode</th>
                <th style={{ padding: '12px 8px', fontWeight: 700 }}>Product Details</th>
                <th style={{ padding: '12px 8px', fontWeight: 700 }}>Category</th>
                <th style={{ padding: '12px 8px', fontWeight: 700 }}>Location</th>
                <th style={{ padding: '12px 8px', fontWeight: 700 }}>Price</th>
                <th style={{ padding: '12px 8px', fontWeight: 700 }}>Stock</th>
                <th style={{ padding: '12px 8px', fontWeight: 700 }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredTableProducts.map(p => {
                const isEditing = editingId === p.id;
                return (
                  <tr key={p.id} style={{ borderBottom: '1px solid #e2e8f0', transition: 'all 0.15s ease' }}>
                    {isEditing ? (
                      <>
                        <td style={{ padding: '6px 8px' }}>
                          <input type="text" value={editBarcode} onChange={e => setEditBarcode(e.target.value)} style={tableInputStyle} />
                        </td>
                        <td style={{ padding: '6px 8px' }}>
                          <input type="text" value={editName} onChange={e => setEditName(e.target.value)} style={tableInputStyle} />
                        </td>
                        <td style={{ padding: '6px 8px' }}>
                          <select value={editCategory} onChange={e => setEditCategory(e.target.value)} style={tableInputStyle}>
                            <option value="Fruits & Vegetables">Fruits & Vegetables</option>
                            <option value="Bakery">Bakery</option>
                            <option value="Dairy & Eggs">Dairy & Eggs</option>
                            <option value="Pantry">Pantry</option>
                          </select>
                        </td>
                        <td style={{ padding: '6px 8px' }}>
                          <input type="text" value={editLocation} onChange={e => setEditLocation(e.target.value)} style={tableInputStyle} />
                        </td>
                        <td style={{ padding: '6px 8px' }}>
                          <input type="number" value={editPrice} onChange={e => setEditPrice(parseFloat(e.target.value) || 0)} style={tableInputStyle} />
                        </td>
                        <td style={{ padding: '6px 8px' }}>
                          <input type="number" value={editStock} onChange={e => setEditStock(parseInt(e.target.value) || 0)} style={tableInputStyle} />
                        </td>
                        <td style={{ padding: '6px 8px', display: 'flex', gap: '6px', alignItems: 'center' }}>
                          <button onClick={() => handleSaveEdit(p.id)} style={{ background: '#059669', border: 'none', color: '#fff', padding: '6px', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center' }} title="Save">
                            <Check size={14} />
                          </button>
                          <button onClick={handleCancelEdit} style={{ background: '#dc2626', border: 'none', color: '#fff', padding: '6px', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center' }} title="Cancel">
                            <X size={14} />
                          </button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td style={{ padding: '12px 8px', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                          {p.barcode}
                        </td>
                        <td style={{ padding: '12px 8px', fontWeight: 'bold' }}>
                          {p.name}
                        </td>
                        <td style={{ padding: '12px 8px', color: 'var(--text-secondary)' }}>
                          {p.category}
                        </td>
                        <td style={{ padding: '12px 8px', color: 'var(--text-secondary)' }}>
                          {p.location}
                        </td>
                        <td style={{ padding: '12px 8px', fontWeight: 'bold' }}>
                          ₹{p.price}
                        </td>
                        <td style={{ padding: '12px 8px', fontWeight: 'bold', color: p.stock < 20 ? '#dc2626' : 'var(--text-primary)' }}>
                          {p.stock}
                        </td>
                        <td style={{ padding: '12px 8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <button onClick={() => startEditProduct(p)} style={{ background: 'transparent', border: 'none', color: '#0c2340', cursor: 'pointer', padding: '4px' }} title="Edit">
                            <Edit size={16} />
                          </button>
                          <button onClick={() => handleDeleteProduct(p.id)} style={{ background: 'transparent', border: 'none', color: '#dc2626', cursor: 'pointer', padding: '4px' }} title="Delete">
                            <Trash2 size={16} />
                          </button>
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Simulated Camera OCR & Barcode Scan Modal */}
      {showScanModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(9, 10, 15, 0.85)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div  style={{
            width: '100%',
            maxWidth: '850px',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            boxShadow: 'var(--shadow-lg)',
            background: 'var(--bg-secondary)',
            border: '1px solid #e2e8f0',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '20px',
              borderBottom: '1px solid #e2e8f0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Camera size={22} style={{ color: '#0c2340' }} /> AI Camera OCR & Barcode Scan
              </h3>
              <button 
                onClick={() => setShowScanModal(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                <X size={24} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1.2fr 1fr',
              gap: '20px',
              padding: '24px',
              maxHeight: '70vh',
              overflowY: 'auto'
            }}>
              {/* Left Column: Viewfinder */}
              <div style={{
                position: 'relative',
                background: '#000',
                borderRadius: 'var(--radius-md)',
                height: '320px',
                overflow: 'hidden',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                border: '2px solid #e2e8f0'
              }}>
                {/* Standby / active feed */}
                <img 
                  src={scanPresets[selectedPresetIndex].imageUrl} 
                  alt="Camera Simulation Feed" 
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                    opacity: isScanning || scannedData ? 0.85 : 0.4,
                    transition: 'opacity 0.3s ease'
                  }}
                />

                {/* Simulated Lens Viewfinder Target Overlay */}
                <div style={{
                  position: 'absolute',
                  width: '70%',
                  height: '70%',
                  border: '2px dashed rgba(255, 255, 255, 0.4)',
                  borderRadius: '12px',
                  pointerEvents: 'none',
                  boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.5)'
                }} />

                {/* Scan animation line */}
                {isScanning && (
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '4px',
                    background: '#059669',
                    boxShadow: '0 0 15px #059669',
                    animation: 'scan-laser-modal 2s infinite linear'
                  }} />
                )}

                {/* Animated Scan laser keyframe styles embedded */}
                <style>{`
                  @keyframes scan-laser-modal {
                    0% { top: 15%; }
                    50% { top: 85%; }
                    100% { top: 15%; }
                  }
                `}</style>

                {/* Floating OCR Bounding Boxes */}
                {isScanning && scanProgress > 40 && (
                  <div style={{
                    position: 'absolute',
                    border: '1.5px solid #059669',
                    background: 'rgba(16, 185, 129, 0.15)',
                    color: '#fff',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '0.65rem',
                    top: '30%',
                    left: '20%',
                    animation: 'pulse 1s infinite'
                  }}>
                    [OCR] {scanPresets[selectedPresetIndex].name.substring(0, 15)}...
                  </div>
                )}
                {isScanning && scanProgress > 60 && (
                  <div style={{
                    position: 'absolute',
                    border: '1.5px solid #0284c7',
                    background: 'rgba(14, 165, 233, 0.15)',
                    color: '#fff',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: '0.65rem',
                    bottom: '25%',
                    right: '25%'
                  }}>
                    [BARCODE] {scanPresets[selectedPresetIndex].barcode}
                  </div>
                )}

                {/* Standby Guidance Text */}
                {!isScanning && !scannedData && (
                  <div style={{
                    position: 'absolute',
                    textAlign: 'center',
                    padding: '20px',
                    color: '#fff',
                    textShadow: '0 2px 4px rgba(0,0,0,0.8)'
                  }}>
                    <Camera size={40} style={{ opacity: 0.6, marginBottom: '8px' }} />
                    <p style={{ fontSize: '0.85rem', fontWeight: 600 }}>Camera Offline</p>
                    <p style={{ fontSize: '0.75rem', opacity: 0.8, marginTop: '4px' }}>Select preset & click Start Scan below</p>
                  </div>
                )}
              </div>

              {/* Right Column: Panel & Controls */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                    Step 1: Choose Product Preset to Place in Front of Lens
                  </label>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '8px',
                    marginTop: '8px'
                  }}>
                    {scanPresets.map((preset, idx) => (
                      <button
                        key={idx}
                        disabled={isScanning}
                        type="button"
                        onClick={() => {
                          setSelectedPresetIndex(idx);
                          setScannedData(null);
                        }}
                        style={{
                          padding: '10px',
                          borderRadius: '8px',
                          border: selectedPresetIndex === idx ? '2px solid #0c2340' : '1px solid #e2e8f0',
                          background: selectedPresetIndex === idx ? 'rgba(79, 70, 229, 0.08)' : 'var(--bg-primary)',
                          color: 'var(--text-primary)',
                          textAlign: 'left',
                          cursor: 'pointer',
                          fontSize: '0.75rem',
                          fontWeight: selectedPresetIndex === idx ? 'bold' : 'normal',
                          opacity: isScanning ? 0.6 : 1
                        }}
                      >
                        {preset.name}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <button
                    disabled={isScanning}
                    type="button"
                    onClick={handleStartScan}
                    className="btn-primary"
                    style={{
                      justifyContent: 'center',
                      padding: '12px',
                      fontSize: '0.85rem'
                    }}
                  >
                    {isScanning ? (
                      <>
                        <Loader2 size={16} className="sync-pulse" style={{ animation: 'spin 1.5s infinite linear' }} />
                        Analyzing via OCR & Barcode... ({scanProgress}%)
                      </>
                    ) : (
                      <>
                        <Scan size={16} /> Simulate Camera OCR Scan
                      </>
                    )}
                  </button>
                </div>

                {/* Progress Logs */}
                <div style={{
                  background: '#090a0f',
                  color: '#10b981',
                  fontFamily: 'monospace',
                  padding: '12px',
                  borderRadius: '8px',
                  fontSize: '0.7rem',
                  height: '110px',
                  overflowY: 'auto',
                  border: '1px solid #1e293b'
                }}>
                  {scanLogs.map((log, i) => (
                    <div key={i} style={{ marginBottom: '4px' }}>{log}</div>
                  ))}
                  {scanLogs.length === 0 && <span style={{ color: '#475569' }}>Console waiting for execution...</span>}
                </div>
              </div>
            </div>

            {/* Scanned Data Results View Footer */}
            {scannedData && (
              <div style={{
                background: 'rgba(16, 185, 129, 0.05)',
                borderTop: '1px solid rgba(16, 185, 129, 0.15)',
                padding: '20px 24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#059669' }}>
                  <Check size={18} />
                  <span style={{ fontSize: '0.85rem', fontWeight: 800 }}>OCR Data Extraction Results:</span>
                </div>
                
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '12px',
                  fontSize: '0.8rem'
                }}>
                  <div>
                    <strong style={{ color: 'var(--text-secondary)' }}>Product Name:</strong>
                    <div style={{ fontWeight: 'bold', marginTop: '2px' }}>{scannedData.name}</div>
                  </div>
                  <div>
                    <strong style={{ color: 'var(--text-secondary)' }}>Price:</strong>
                    <div style={{ fontWeight: 'bold', marginTop: '2px' }}>₹{scannedData.price}</div>
                  </div>
                  <div>
                    <strong style={{ color: 'var(--text-secondary)' }}>Barcode:</strong>
                    <div style={{ fontWeight: 'bold', marginTop: '2px', fontFamily: 'monospace' }}>{scannedData.barcode}</div>
                  </div>
                  <div>
                    <strong style={{ color: 'var(--text-secondary)' }}>Category:</strong>
                    <div style={{ fontWeight: 'bold', marginTop: '2px' }}>{scannedData.category}</div>
                  </div>
                  <div>
                    <strong style={{ color: 'var(--text-secondary)' }}>Location:</strong>
                    <div style={{ fontWeight: 'bold', marginTop: '2px' }}>{scannedData.location}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '4px' }}>
                  <button 
                    type="button"
                    onClick={() => {
                      setScannedData(null);
                      setScanLogs([]);
                    }} 
                    className="btn-secondary" 
                    style={{ padding: '8px 16px', fontSize: '0.8rem' }}
                  >
                    Clear
                  </button>
                  <button 
                    type="button"
                    onClick={handleApplyScannedData} 
                    className="btn-primary" 
                    style={{ padding: '8px 20px', fontSize: '0.8rem' }}
                  >
                    Populate form & review
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
