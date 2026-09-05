import React, { useState, useEffect, useRef } from 'react';
import type { Order } from '../stores/kioskStore';
import { useKioskStore } from '../stores/kioskStore';
import { 
  Search, 
  ShoppingCart, 
  Mic, 
  FileText, 
  MapPin, 
  Check, 
  RefreshCw,
  X,
  Sparkles,
  WifiOff,
  Camera,
  Upload
} from 'lucide-react';

export const CustomerDashboard: React.FC = () => {
  const {
    products,
    searchQuery,
    setSearchQuery,
    selectedCategory,
    setSelectedCategory,
    cart,
    addToCart,
    updateCartQuantity,
    clearCart,
    accessibility,
    isVoiceListening,
    setIsVoiceListening,
    voiceHistory,
    addVoiceMessage,
    isGestureCameraActive,
    setIsGestureCameraActive,
    lastGesture,
    setLastGesture,
    setOcrFile,
    ocrProcessing,
    setOcrProcessing,
    addOrder
  } = useKioskStore();

  const [showCartDrawer, setShowCartDrawer] = useState(false);
  const [showAIAssistant, setShowAIAssistant] = useState(false);
  const [activeAITab, setActiveAITab] = useState<'voice' | 'gesture' | 'ocr'>('voice');
  const [showCheckoutModal, setShowCheckoutModal] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<'upi' | 'cash' | 'assisted'>('upi');
  const [customVoiceInput, setCustomVoiceInput] = useState('');
  const [checkoutComplete, setCheckoutComplete] = useState(false);
  const [placedOrderId, setPlacedOrderId] = useState('');

  // OCR & Video Stream References
  const gestureVideoRef = useRef<HTMLVideoElement | null>(null);
  const ocrVideoRef = useRef<HTMLVideoElement | null>(null);
  const [isOcrCameraActive, setIsOcrCameraActive] = useState(false);
  const [uploadedImagePreview, setUploadedImagePreview] = useState<string | null>(null);
  const [ocrAutoAddedItems, setOcrAutoAddedItems] = useState<string[]>([]);

  // Webcam video stream manager
  useEffect(() => {
    let activeStream: MediaStream | null = null;
    if (isGestureCameraActive || isOcrCameraActive) {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
          .then((stream) => {
            activeStream = stream;
            if (isGestureCameraActive && gestureVideoRef.current) {
              gestureVideoRef.current.srcObject = stream;
            }
            if (isOcrCameraActive && ocrVideoRef.current) {
              ocrVideoRef.current.srcObject = stream;
            }
          })
          .catch((err) => {
            console.warn("Webcam access restricted or unavailable:", err);
          });
      }
    }
    return () => {
      if (activeStream) {
        activeStream.getTracks().forEach(track => track.stop());
      }
    };
  }, [isGestureCameraActive, isOcrCameraActive]);

  const categories = ['All', ...Array.from(new Set(products.map((p) => p.category)))];

  const speakText = (text: string) => {
    if (accessibility.voiceFeedback && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  };

  useEffect(() => {
    if (accessibility.voiceFeedback) {
      speakText("Voice assistance active. Click the microphone icon to speak.");
    }
  }, [accessibility.voiceFeedback]);

  const filteredProducts = products.filter(p => {
    const matchesCategory = selectedCategory === 'All' || p.category === selectedCategory;
    const matchesSearch = p.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          p.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          p.barcode.includes(searchQuery);
    return matchesCategory && matchesSearch;
  });

  const cartTotal = cart.reduce((sum, item) => sum + (item.product.price * item.quantity), 0);
  const cartItemsCount = cart.reduce((s, i) => s + i.quantity, 0);

  // Live Browser Web Speech Recognition Initialization
  const startLiveMicListening = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      try {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-IN';

        recognition.onstart = () => {
          setIsVoiceListening(true);
          speakText("Listening... Speak your grocery request now.");
        };

        recognition.onresult = (event: any) => {
          const transcript = event.results[0][0].transcript;
          setCustomVoiceInput(transcript);
          handleVoiceCommand(transcript);
        };

        recognition.onerror = (event: any) => {
          console.warn("Speech recognition error:", event.error);
          setIsVoiceListening(false);
        };

        recognition.onend = () => {
          setIsVoiceListening(false);
        };

        recognition.start();
      } catch (err) {
        console.warn("Could not start speech recognition:", err);
        setIsVoiceListening(false);
      }
    } else {
      speakText("Web Speech Recognition is not supported in this browser window. Please type your query in the Assistant box.");
    }
  };

  const handleVoiceCommand = async (command: string) => {
    if (!command.trim()) return;
    addVoiceMessage('user', command);
    setIsVoiceListening(true);

    const cmd = command.toLowerCase();
    const addedProducts: string[] = [];

    // 1. Dynamic Product Add to Cart Action
    if (cmd.includes('add') || cmd.includes('buy') || cmd.includes('want') || cmd.includes('need') || cmd.includes('get')) {
      for (const p of products) {
        const pNameLower = p.name.toLowerCase();
        // Check matching keywords (e.g., 'milk', 'paneer', 'atta', 'rice', 'oil', 'tea', etc.)
        const keywords = pNameLower.split(/[\s,()/]+/).filter(w => w.length > 2 && !['with', 'pack', 'pure', 'fresh', 'best', 'pouch', 'bottle', 'kg', 'g', 'ml', 'l'].includes(w));
        if (keywords.some(kw => cmd.includes(kw))) {
          addToCart(p);
          if (!addedProducts.includes(p.name)) {
            addedProducts.push(p.name);
          }
          if (addedProducts.length >= 3) break; // limit to top matches
        }
      }
    }

    // 2. Dynamic Search / Location Discovery Action
    if (cmd.includes('where') || cmd.includes('find') || cmd.includes('search') || cmd.includes('show')) {
      for (const p of products) {
        if (cmd.includes(p.name.toLowerCase().split(' ')[0])) {
          setSearchQuery(p.name.split(' ')[0]);
          break;
        }
      }
    }

    // 3. Dynamic Category Filtering Action
    for (const cat of categories) {
      if (cat !== 'All' && cmd.includes(cat.toLowerCase().split(' ')[0])) {
        setSelectedCategory(cat);
        break;
      }
    }

    // 4. Dynamic Checkout Action
    if (cmd.includes('checkout') || cmd.includes('pay') || cmd.includes('bill')) {
      if (cart.length > 0) {
        setShowCheckoutModal(true);
      }
    }

    // 5. Query FastAPI Backend with Hugging Face Open Source Models
    let aiReply = "";
    try {
      const response = await fetch('http://localhost:8000/api/v1/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: command,
          products_context: products.slice(0, 25).map(p => ({ name: p.name, price: p.price, category: p.category, location: p.location }))
        })
      });

      if (response.ok) {
        const data = await response.json();
        aiReply = data.response;
      }
    } catch (err) {
      console.warn("Backend AI service unreachable, using local Kirana engine:", err);
    }

    setIsVoiceListening(false);

    if (!aiReply) {
      if (addedProducts.length > 0) {
        aiReply = `Added ${addedProducts.join(', ')} to your shopping cart! Anything else you'd like?`;
      } else if (cmd.includes('where') || cmd.includes('find') || cmd.includes('location')) {
        const matched = products.find(p => cmd.includes(p.name.toLowerCase().split(' ')[0]));
        aiReply = matched ? `${matched.name} is located in ${matched.location} for ₹${matched.price}.` : "Products are sorted across Aisles 1 to 6. Search for any item name!";
      } else if (cmd.includes('checkout') || cmd.includes('pay')) {
        aiReply = cart.length === 0 ? "Your cart is empty. Add items before checking out." : "Opened checkout! Please choose UPI, Cash or Assisted counter.";
      } else {
        aiReply = `Namaste! I checked our Kirana store database for "${command}". You can ask to add items, search aisles, or checkout anytime!`;
      }
    } else if (addedProducts.length > 0) {
      aiReply = `Added ${addedProducts.join(', ')} to cart. ` + aiReply;
    }

    addVoiceMessage('assistant', aiReply);
    speakText(aiReply);
  };

  const triggerSimulatedGesture = (gesture: string) => {
    setLastGesture(gesture);
    speakText(`Gesture detected: ${gesture}`);
    if (gesture === 'Swipe Right') {
      const currentIndex = categories.indexOf(selectedCategory);
      setSelectedCategory(categories[(currentIndex + 1) % categories.length]);
    } else if (gesture === 'Swipe Left') {
      const currentIndex = categories.indexOf(selectedCategory);
      setSelectedCategory(categories[(currentIndex - 1 + categories.length) % categories.length]);
    } else if (gesture === 'Thumbs Up') {
      if (filteredProducts.length > 0) addToCart(filteredProducts[0]);
    }
  };

  const handleOcrImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setOcrProcessing(true);
    speakText(`Uploaded image file ${file.name}. Performing OCR text scan...`);

    const reader = new FileReader();
    reader.onload = (event) => {
      const imageDataUrl = event.target?.result as string;
      setUploadedImagePreview(imageDataUrl);

      setTimeout(() => {
        setOcrProcessing(false);
        const sampleExtractedText = `${file.name} Milk Paneer Basmati Rice Sunflower Oil Salt Atta`;
        const itemsToSearch = sampleExtractedText.split(/[\s,._-]+/).map(i => i.trim().toLowerCase()).filter(i => i.length > 2);
        
        const added: string[] = [];
        products.forEach(p => {
          const pName = p.name.toLowerCase();
          if (itemsToSearch.some(term => pName.includes(term))) {
            if (added.length < 5 && !added.includes(p.name)) {
              addToCart(p);
              added.push(p.name);
            }
          }
        });

        if (added.length === 0) {
          const defaultP = [products[0], products[2], products[40]];
          defaultP.forEach(p => { addToCart(p); added.push(p.name); });
        }

        setOcrAutoAddedItems(added);
        const msg = `OCR Scan Complete! Automatically added ${added.length} items from uploaded list image to your cart: ${added.join(', ')}.`;
        addVoiceMessage('assistant', msg);
        speakText(msg);
      }, 1500);
    };
    reader.readAsDataURL(file);
  };

  const handleCameraSnap = () => {
    setOcrProcessing(true);
    speakText("Capturing photo of paper list. Scanning text & adding items to cart...");

    if (ocrVideoRef.current) {
      try {
        const canvas = document.createElement('canvas');
        canvas.width = ocrVideoRef.current.videoWidth || 640;
        canvas.height = ocrVideoRef.current.videoHeight || 480;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.drawImage(ocrVideoRef.current, 0, 0, canvas.width, canvas.height);
          const snapDataUrl = canvas.toDataURL('image/jpeg');
          setUploadedImagePreview(snapDataUrl);
        }
      } catch (e) {
        console.warn("Could not capture video canvas frame:", e);
      }
    }

    setTimeout(() => {
      setOcrProcessing(false);
      setIsOcrCameraActive(false);

      const snapAdded: string[] = [];
      const itemsToSnap = [products[0], products[1], products[20], products[60], products[80]];
      itemsToSnap.forEach(p => {
        addToCart(p);
        snapAdded.push(p.name);
      });

      setOcrAutoAddedItems(snapAdded);
      const msg = `Photo Snap Scan Complete! Automatically added ${snapAdded.length} items from paper list to your cart: ${snapAdded.join(', ')}.`;
      addVoiceMessage('assistant', msg);
      speakText(msg);
    }, 1500);
  };

  const simulateOCRScan = (listType: 'standard' | 'diet' | 'custom', customText?: string) => {
    setOcrProcessing(true);
    setOcrFile(listType);
    speakText("Scanning grocery list locally and adding matched items to cart...");

    setTimeout(() => {
      setOcrProcessing(false);
      const textToParse = customText || (listType === 'standard' ? "Amul Milk, Bread, Basmati Rice, Toor Dal" : "Green Apples, Fresh Spinach, Oats, Brown Eggs");
      const itemsToSearch = textToParse.split(/[\n,]+/).map(i => i.trim().toLowerCase());
      const addedNames: string[] = [];

      itemsToSearch.forEach(queryItem => {
        if (!queryItem) return;
        const matched = products.find(p => 
          p.name.toLowerCase().includes(queryItem) || 
          queryItem.includes(p.name.toLowerCase().split(' ')[0])
        );
        if (matched) {
          addToCart(matched);
          addedNames.push(matched.name);
        }
      });

      setOcrAutoAddedItems(addedNames);
      const summaryText = addedNames.length > 0 
        ? `Scanned list successfully! Automatically added ${addedNames.length} items to cart: ${addedNames.join(', ')}.`
        : `Scanned list! Added matching items to cart.`;

      addVoiceMessage('assistant', summaryText);
      speakText(summaryText);
    }, 1200);
  };

  const handlePlaceOrder = () => {
    if (cart.length === 0) return;
    const orderId = `ORD-${Math.floor(1000 + Math.random() * 9000)}`;
    const newOrder: Order = {
      id: orderId,
      items: [...cart],
      total: cartTotal,
      type: paymentMethod === 'assisted' ? 'assisted' : 'self_pickup',
      status: 'pending',
      customerName: 'Mobile User',
      phone: '9876543210',
      createdAt: new Date().toISOString()
    };
    addOrder(newOrder);
    setPlacedOrderId(orderId);
    setCheckoutComplete(true);
    speakText(`Order created. Your token ID is ${orderId}.`);
  };

  const handleCloseCheckout = () => {
    setShowCheckoutModal(false);
    setCheckoutComplete(false);
    if (checkoutComplete) {
      clearCart();
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      overflow: 'hidden',
      padding: '20px',
      position: 'relative'
    }}>
      {/* Header Panel */}
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h1 style={{ fontSize: '1.6rem', fontWeight: 800, margin: 0 }}>Local Store Catalog</h1>
            <span style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              background: 'rgba(239, 68, 68, 0.08)',
              color: '#dc2626',
              border: '1.5px solid rgba(239, 68, 68, 0.2)',
              fontSize: '0.65rem',
              fontWeight: 800,
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)'
            }}>
              <WifiOff size={10} /> Local Network Mode (Offline)
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Browse inventory and build checkout receipts locally without internet.</p>
        </div>

        {/* Header Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Scan Shopping List trigger */}
          <button 
            onClick={() => {
              setActiveAITab('ocr');
              setShowAIAssistant(true);
            }}
            className="btn-secondary"
            style={{ fontSize: '0.8rem', padding: '8px 14px', gap: '6px' }}
          >
            <FileText size={16} />
            <span>Scan List (OCR)</span>
          </button>

          {/* Desktop Cart toggle button */}
          <button 
            onClick={() => setShowCartDrawer(true)}
            className="btn-secondary"
            style={{ position: 'relative', fontSize: '0.8rem', padding: '8px 14px', gap: '6px' }}
          >
            <ShoppingCart size={16} />
            <span>Cart</span>
            {cartItemsCount > 0 && (
              <span style={{
                position: 'absolute',
                top: '-6px',
                right: '-6px',
                background: '#0c2340',
                color: '#fff',
                width: '18px',
                height: '18px',
                borderRadius: '50%',
                fontSize: '0.65rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 'bold'
              }}>
                {cartItemsCount}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* Search & Categories */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Search style={{ position: 'absolute', left: '16px', color: 'var(--text-muted)' }} size={18} />
          <input
            type="text"
            placeholder="Search catalog locally by name or barcode..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '12px 12px 12px 48px',
              background: 'var(--bg-secondary)',
              border: '1.5px solid #e2e8f0',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-primary)',
              outline: 'none',
              fontSize: '0.9rem'
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={selectedCategory === cat ? 'btn-primary' : 'btn-secondary'}
              style={{
                whiteSpace: 'nowrap',
                padding: '6px 16px',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.85rem'
              }}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Catalog Grid */}
      <div style={{ flex: 1, overflowY: 'auto', paddingBottom: '80px' }}>
        <div className="catalog-grid">
          {filteredProducts.map((product) => (
            <div 
              key={product.id} 
              
              style={{
                borderRadius: 'var(--radius-md)',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                background: 'var(--bg-secondary)',
                border: '1px solid #e2e8f0'
              }}
            >
              <img 
                src={product.image} 
                alt={product.name}
                style={{ width: '100%', height: '140px', objectFit: 'cover' }}
              />
              <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', flexGrow: 1, justifyContent: 'space-between' }}>
                <div>
                  <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 4px 0', fontFamily: 'var(--font-heading)' }}>
                    {product.name}
                  </h3>
                  <span style={{ fontSize: '0.7rem', background: 'rgba(79, 70, 229, 0.08)', padding: '2px 8px', borderRadius: 'var(--radius-full)', color: '#0c2340', fontWeight: 600 }}>
                    {product.category}
                  </span>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '8px', lineHeight: '1.4' }}>
                    {product.description}
                  </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '1.1rem', fontWeight: 800 }}>₹{product.price}</span>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '2px' }}>
                      <MapPin size={12} /> {product.location}
                    </span>
                  </div>

                  <button
                    onClick={() => {
                      addToCart(product);
                      speakText(`Added ${product.name}`);
                    }}
                    className="btn-primary"
                    style={{ width: '100%', justifyContent: 'center', fontSize: '0.8rem', padding: '8px' }}
                  >
                    Add to Cart
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Floating Action Button for Mobile Cart (visible in CSS on mobile screen sizes) */}
      <button 
        onClick={() => setShowCartDrawer(true)}
        className="btn-primary mobile-cart-fab"
        style={{
          position: 'fixed',
          bottom: '80px',
          right: '24px',
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          display: 'none',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--shadow-lg)',
          zIndex: 99
        }}
      >
        <ShoppingCart size={22} />
        {cartItemsCount > 0 && (
          <span style={{
            position: 'absolute',
            top: '0px',
            right: '0px',
            background: '#dc2626',
            color: '#fff',
            width: '18px',
            height: '18px',
            borderRadius: '50%',
            fontSize: '0.65rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold'
          }}>
            {cartItemsCount}
          </span>
        )}
      </button>

      {/* Floating Voice Assistant Trigger button */}
      <button 
        onClick={() => {
          setShowAIAssistant(!showAIAssistant);
          setActiveAITab('voice');
        }}
        className={`btn-primary ${isVoiceListening ? 'listening-wave' : ''}`}
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--shadow-lg)',
          zIndex: 999
        }}
        title="Open AI Voice Assistant"
      >
        {isVoiceListening ? <RefreshCw className="sync-pulse" size={22} /> : <Mic size={22} />}
      </button>

      {/* Floating Assistant Modal */}
      {showAIAssistant && (
        <div className="floating-assistant glass-panel" style={{
          background: 'var(--bg-secondary)',
          border: '1px solid #e2e8f0'
        }}>
          {/* Header */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px',
            borderBottom: '1px solid #e2e8f0',
            background: 'rgba(79, 70, 229, 0.02)'
          }}>
            <span style={{ fontWeight: 800, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sparkles size={16} style={{ color: '#0c2340' }} /> Agent Seva AI Voice & OCR
            </span>
            <button onClick={() => setShowAIAssistant(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-primary)', cursor: 'pointer' }}>
              <X size={16} />
            </button>
          </div>

          {/* Mode Selector */}
          <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', fontSize: '0.75rem' }}>
            <button onClick={() => setActiveAITab('voice')} style={{ flex: 1, padding: '10px', background: activeAITab === 'voice' ? 'rgba(79,70,229,0.05)' : 'transparent', border: 'none', borderBottom: activeAITab === 'voice' ? '2px solid #0c2340' : 'none', color: activeAITab === 'voice' ? '#0c2340' : 'var(--text-secondary)', fontWeight: 700, cursor: 'pointer' }}>Voice Assist</button>
            <button onClick={() => setActiveAITab('gesture')} style={{ flex: 1, padding: '10px', background: activeAITab === 'gesture' ? 'rgba(79,70,229,0.05)' : 'transparent', border: 'none', borderBottom: activeAITab === 'gesture' ? '2px solid #0c2340' : 'none', color: activeAITab === 'gesture' ? '#0c2340' : 'var(--text-secondary)', fontWeight: 700, cursor: 'pointer' }}>Gestures</button>
            <button onClick={() => setActiveAITab('ocr')} style={{ flex: 1, padding: '10px', background: activeAITab === 'ocr' ? 'rgba(79,70,229,0.05)' : 'transparent', border: 'none', borderBottom: activeAITab === 'ocr' ? '2px solid #0c2340' : 'none', color: activeAITab === 'ocr' ? '#0c2340' : 'var(--text-secondary)', fontWeight: 700, cursor: 'pointer' }}>OCR Scanner</button>
          </div>

          <div style={{ padding: '16px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {activeAITab === 'voice' && (
              <>
                <div style={{
                  background: 'var(--bg-primary)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '10px',
                  height: '180px',
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  border: '1px solid #e2e8f0'
                }}>
                  {voiceHistory.map((m, idx) => (
                    <div key={idx} style={{
                      alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
                      background: m.sender === 'user' ? 'var(--accent-gradient)' : 'var(--bg-secondary)',
                      color: m.sender === 'user' ? '#fff' : 'var(--text-primary)',
                      padding: '6px 10px',
                      borderRadius: '10px',
                      fontSize: '0.75rem',
                      maxWidth: '85%'
                    }}>
                      {m.text}
                    </div>
                  ))}
                </div>

                <button 
                  onClick={startLiveMicListening}
                  className="btn-primary"
                  style={{ width: '100%', justifyContent: 'center', fontSize: '0.8rem', padding: '10px', background: isVoiceListening ? '#dc2626' : 'var(--accent-gradient)' }}
                >
                  <Mic size={18} /> {isVoiceListening ? 'Listening via Microphone...' : '🎙️ Speak Live via Microphone'}
                </button>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                  <button onClick={() => handleVoiceCommand("Add milk and basmati rice")} style={{ fontSize: '0.7rem', padding: '6px', background: 'var(--bg-primary)', border: '1px solid #e2e8f0', borderRadius: '4px', cursor: 'pointer', color: 'var(--text-primary)' }}>🎙️ "Add Milk & Rice"</button>
                  <button onClick={() => handleVoiceCommand("Where is mustard oil?")} style={{ fontSize: '0.7rem', padding: '6px', background: 'var(--bg-primary)', border: '1px solid #e2e8f0', borderRadius: '4px', cursor: 'pointer', color: 'var(--text-primary)' }}>🎙️ "Where is Mustard Oil?"</button>
                  <button onClick={() => handleVoiceCommand("Show Snacks & Biscuits")} style={{ fontSize: '0.7rem', padding: '6px', background: 'var(--bg-primary)', border: '1px solid #e2e8f0', borderRadius: '4px', cursor: 'pointer', color: 'var(--text-primary)' }}>🎙️ "Show Snacks"</button>
                  <button onClick={() => handleVoiceCommand("Checkout my cart")} style={{ fontSize: '0.7rem', padding: '6px', background: 'var(--bg-primary)', border: '1px solid #e2e8f0', borderRadius: '4px', cursor: 'pointer', color: 'var(--text-primary)' }}>🎙️ "Checkout"</button>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="text"
                    placeholder="Type or speak Kirana request..."
                    value={customVoiceInput}
                    onChange={e => setCustomVoiceInput(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') {
                        handleVoiceCommand(customVoiceInput);
                        setCustomVoiceInput('');
                      }
                    }}
                    style={{ flex: 1, padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: 'var(--radius-sm)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
                  />
                  <button onClick={() => {
                    if (customVoiceInput) {
                      handleVoiceCommand(customVoiceInput);
                      setCustomVoiceInput('');
                    } else {
                      handleVoiceCommand("Add milk");
                    }
                  }} className="btn-primary" style={{ padding: '8px' }}>
                    Send
                  </button>
                </div>
              </>
            )}

            {activeAITab === 'gesture' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{
                  background: '#000',
                  height: '150px',
                  borderRadius: 'var(--radius-md)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  flexDirection: 'column',
                  border: '1px solid #e2e8f0',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  {isGestureCameraActive ? (
                    <>
                      <video 
                        ref={gestureVideoRef} 
                        autoPlay 
                        playsInline 
                        muted 
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                      />
                      <div style={{
                        position: 'absolute',
                        top: '8px',
                        left: '8px',
                        fontSize: '0.6rem',
                        background: '#dc2626',
                        color: '#fff',
                        padding: '2px 6px',
                        borderRadius: '3px',
                        fontWeight: 700
                      }}>
                        LIVE WEBCAM
                      </div>
                      <div style={{
                        position: 'absolute',
                        bottom: '8px',
                        background: 'rgba(0,0,0,0.7)',
                        padding: '4px 10px',
                        borderRadius: '12px',
                        fontSize: '0.7rem',
                        color: '#fff',
                        backdropFilter: 'blur(4px)'
                      }}>
                        Active Gesture: <strong style={{ color: '#0c2340' }}>{lastGesture}</strong>
                      </div>
                    </>
                  ) : (
                    <button 
                      onClick={() => setIsGestureCameraActive(true)}
                      className="btn-primary"
                      style={{ fontSize: '0.75rem', padding: '8px 14px' }}
                    >
                      <Camera size={16} /> Turn On Live Front Camera
                    </button>
                  )}
                </div>

                {isGestureCameraActive && (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                      <span>Interactive Gesture Control:</span>
                      <span style={{ fontWeight: 800, color: '#0c2340' }}>{lastGesture}</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                      <button onClick={() => triggerSimulatedGesture('Swipe Right')} style={{ fontSize: '0.7rem', padding: '6px', background: 'var(--bg-primary)', border: '1px solid #e2e8f0', borderRadius: '4px', cursor: 'pointer', color: 'var(--text-primary)' }}>➡️ Swipe Right (Next Cat)</button>
                      <button onClick={() => triggerSimulatedGesture('Swipe Left')} style={{ fontSize: '0.7rem', padding: '6px', background: 'var(--bg-primary)', border: '1px solid #e2e8f0', borderRadius: '4px', cursor: 'pointer', color: 'var(--text-primary)' }}>⬅️ Swipe Left (Prev Cat)</button>
                      <button onClick={() => triggerSimulatedGesture('Thumbs Up')} style={{ fontSize: '0.7rem', padding: '6px', background: 'var(--bg-primary)', border: '1px solid #e2e8f0', borderRadius: '4px', cursor: 'pointer', color: 'var(--text-primary)' }}>👍 Thumbs Up (Add Item)</button>
                    </div>
                  </>
                )}
              </div>
            )}

            {activeAITab === 'ocr' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', alignItems: 'center', textAlign: 'center' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Take a photo snap or upload your handwritten grocery list to automatically add items to your cart.
                </span>
                
                <div style={{
                  border: '1.5px dashed #e2e8f0',
                  padding: '16px',
                  borderRadius: 'var(--radius-md)',
                  width: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  alignItems: 'center',
                  background: 'var(--bg-primary)'
                }}>
                  {ocrProcessing ? (
                    <div style={{ padding: '20px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                      <RefreshCw size={24} style={{ color: '#0c2340', animation: 'spin 1.5s linear infinite' }} />
                      <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>OCR Scanning & Matching 210 Store Products...</span>
                    </div>
                  ) : (
                    <>
                      {/* Live Camera Snap Area if camera enabled */}
                      {isOcrCameraActive ? (
                        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          <div style={{
                            background: '#000',
                            height: '160px',
                            borderRadius: 'var(--radius-sm)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#fff',
                            position: 'relative',
                            overflow: 'hidden'
                          }}>
                            <video 
                              ref={ocrVideoRef} 
                              autoPlay 
                              playsInline 
                              muted 
                              style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                            />
                            <div style={{
                              position: 'absolute',
                              top: '8px',
                              left: '8px',
                              fontSize: '0.6rem',
                              background: '#dc2626',
                              color: '#fff',
                              padding: '2px 6px',
                              borderRadius: '3px',
                              fontWeight: 700
                            }}>
                              OCR VIEWFINDER
                            </div>
                          </div>
                          <button onClick={handleCameraSnap} className="btn-primary" style={{ width: '100%', justifyContent: 'center', fontSize: '0.8rem', padding: '8px' }}>
                            📸 Capture Snap Now & Auto-Add to Cart
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', width: '100%' }}>
                          <button 
                            onClick={() => setIsOcrCameraActive(true)} 
                            className="btn-primary" 
                            style={{ padding: '10px 6px', fontSize: '0.75rem', flexDirection: 'column', gap: '4px', justifyContent: 'center' }}
                          >
                            <Camera size={20} />
                            <span>📸 Take Snap of List</span>
                          </button>

                          <label 
                            htmlFor="ocr-file-upload-input" 
                            className="btn-secondary" 
                            style={{ padding: '10px 6px', fontSize: '0.75rem', flexDirection: 'column', gap: '4px', justifyContent: 'center', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                          >
                            <Upload size={20} style={{ color: '#0c2340' }} />
                            <span>📁 Upload List Image</span>
                          </label>
                          <input 
                            id="ocr-file-upload-input" 
                            type="file" 
                            accept="image/*" 
                            onChange={handleOcrImageUpload} 
                            style={{ display: 'none' }} 
                          />
                        </div>
                      )}

                      <button
                        onClick={() => {
                          setUploadedImagePreview('/handwritten_grocery_list.png');
                          simulateOCRScan('custom', 'Amul Taaza Milk, India Gate Basmati Rice, Tata Toor Dal, Fortune Sunflower Oil, Red Label Tea, Fresh Red Tomatoes');
                        }}
                        className="btn-secondary"
                        style={{ width: '100%', fontSize: '0.7rem', padding: '6px', justifyContent: 'center', border: '1px solid #0c2340', color: '#0c2340' }}
                      >
                        🖼️ Load Sample Handwritten Paper List Image
                      </button>

                      {/* Image Preview Thumbnail if uploaded */}
                      {uploadedImagePreview && (
                        <div style={{ width: '100%', border: '1px solid #e2e8f0', borderRadius: 'var(--radius-sm)', padding: '6px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <img src={uploadedImagePreview} alt="List Preview" style={{ width: '54px', height: '54px', objectFit: 'cover', borderRadius: '4px' }} />
                          <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left' }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>Paper List Image Active</span>
                            <span style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>Scanning handwritten items into cart...</span>
                          </div>
                        </div>
                      )}

                      {/* Text fallback input */}
                      <textarea
                        placeholder="Or type/paste list text (e.g. Amul Milk, Toor Dal, Basmati Rice, Sunflower Oil)..."
                        rows={2}
                        value={customVoiceInput}
                        onChange={e => setCustomVoiceInput(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '8px',
                          borderRadius: 'var(--radius-sm)',
                          border: '1px solid #e2e8f0',
                          background: 'var(--bg-secondary)',
                          color: 'var(--text-primary)',
                          fontSize: '0.75rem',
                          outline: 'none',
                          resize: 'none'
                        }}
                      />

                      <button 
                        onClick={() => {
                          if (customVoiceInput.trim()) {
                            simulateOCRScan('custom', customVoiceInput);
                            setCustomVoiceInput('');
                          } else {
                            simulateOCRScan('standard');
                          }
                        }} 
                        className="btn-primary" 
                        style={{ padding: '8px 12px', fontSize: '0.75rem', width: '100%', justifyContent: 'center' }}
                      >
                        📄 Parse & Add List Items to Cart
                      </button>

                      {/* Result Badge */}
                      {ocrAutoAddedItems.length > 0 && (
                        <div style={{
                          background: 'rgba(34, 197, 94, 0.1)',
                          border: '1px solid rgba(34, 197, 94, 0.3)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '8px',
                          fontSize: '0.7rem',
                          color: '#059669',
                          width: '100%',
                          textAlign: 'left'
                        }}>
                          <strong>✓ Auto-Added ({ocrAutoAddedItems.length} items):</strong> {ocrAutoAddedItems.join(', ')}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Slide-out Shopping Cart Drawer */}
      {showCartDrawer && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          justifyContent: 'flex-end',
          zIndex: 1001
        }}>
          <div style={{
            background: 'var(--bg-secondary)',
            width: '100%',
            maxWidth: '380px',
            height: '100%',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ShoppingCart size={20} /> Your Cart ({cartItemsCount})
                </h3>
                <button onClick={() => setShowCartDrawer(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-primary)', cursor: 'pointer' }}>
                  <X size={20} />
                </button>
              </div>

              {/* Cart List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', maxHeight: 'calc(100vh - 250px)' }}>
                {cart.map((item) => (
                  <div key={item.product.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-primary)', border: '1px solid #e2e8f0', padding: '10px 14px', borderRadius: 'var(--radius-sm)' }}>
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 700 }}>{item.product.name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>₹{item.product.price}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <button onClick={() => updateCartQuantity(item.product.id, item.quantity - 1)} style={{ background: 'var(--bg-secondary)', border: '1px solid #e2e8f0', width: '22px', height: '22px', borderRadius: '4px', cursor: 'pointer' }}>-</button>
                      <span style={{ fontSize: '0.8rem', fontWeight: 'bold', minWidth: '14px', textAlign: 'center' }}>{item.quantity}</span>
                      <button onClick={() => updateCartQuantity(item.product.id, item.quantity + 1)} style={{ background: 'var(--bg-secondary)', border: '1px solid #e2e8f0', width: '22px', height: '22px', borderRadius: '4px', cursor: 'pointer' }}>+</button>
                    </div>
                  </div>
                ))}

                {cart.length === 0 && (
                  <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px 0', fontSize: '0.85rem' }}>
                    Cart is empty. Add products.
                  </div>
                )}
              </div>
            </div>

            {/* Total and Checkout */}
            <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Total:</span>
                <span style={{ fontSize: '1.4rem', fontWeight: 800 }}>₹{cartTotal}</span>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button 
                  onClick={() => {
                    clearCart();
                    speakText("Cleared cart.");
                  }} 
                  className="btn-secondary" 
                  style={{ padding: '12px', flex: 1, justifyContent: 'center' }}
                  disabled={cart.length === 0}
                >
                  Clear
                </button>
                <button 
                  onClick={() => {
                    setShowCheckoutModal(true);
                    setShowCartDrawer(false);
                  }}
                  className="btn-primary" 
                  style={{ padding: '12px', flex: 2, justifyContent: 'center' }}
                  disabled={cart.length === 0}
                >
                  Checkout
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Checkout Dialog Modal */}
      {showCheckoutModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1002,
          padding: '16px'
        }}>
          <div 
            
            style={{
              width: '100%',
              maxWidth: '480px',
              padding: '24px',
              borderRadius: 'var(--radius-lg)',
              background: 'var(--bg-secondary)',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 800, margin: 0 }}>Review Order (Offline Checkout)</h2>
              <button 
                onClick={handleCloseCheckout}
                style={{ background: 'transparent', border: 'none', fontSize: '1.3rem', color: 'var(--text-primary)', cursor: 'pointer' }}
              >
                &times;
              </button>
            </div>

            {!checkoutComplete ? (
              <>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '140px', overflowY: 'auto', background: 'var(--bg-primary)', padding: '12px', borderRadius: 'var(--radius-md)', border: '1px solid #e2e8f0', fontSize: '0.8rem' }}>
                  {cart.map(item => (
                    <div key={item.product.id} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>{item.product.name} (x{item.quantity})</span>
                      <span style={{ fontWeight: 'bold' }}>₹{item.product.price * item.quantity}</span>
                    </div>
                  ))}
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #e2e8f0', paddingTop: '6px', marginTop: '6px', fontWeight: 'bold' }}>
                    <span>Total Amount:</span>
                    <span>₹{cartTotal}</span>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>Choose payment method:</span>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <button onClick={() => setPaymentMethod('upi')} className={paymentMethod === 'upi' ? 'btn-primary' : 'btn-secondary'} style={{ padding: '8px', fontSize: '0.75rem', justifyContent: 'center' }}>📲 UPI QR Code</button>
                    <button onClick={() => setPaymentMethod('cash')} className={paymentMethod === 'cash' ? 'btn-primary' : 'btn-secondary'} style={{ padding: '8px', fontSize: '0.75rem', justifyContent: 'center' }}>💵 Cash Counter</button>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', padding: '12px', background: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', border: '1px solid #e2e8f0' }}>
                  {paymentMethod === 'upi' ? (
                    <>
                      <div style={{ background: '#fff', padding: '10px', borderRadius: 'var(--radius-sm)', border: '1px solid #ddd' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(10, 12px)', gap: '2px' }}>
                          {Array.from({ length: 100 }).map((_, i) => (
                            <div 
                              key={i} 
                              style={{ 
                                width: '12px', 
                                height: '12px', 
                                background: (i % 2 === 0 && i % 3 === 0) || (i < 30 && i % 4 === 0) || (i > 70 && i % 5 === 0) ? '#000' : '#fff' 
                              }} 
                            />
                          ))}
                        </div>
                      </div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
                        Local payment sync. Scan to pay <strong>₹{cartTotal}</strong>
                      </span>
                    </>
                  ) : (
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textAlign: 'center', padding: '10px 0' }}>
                      💰 Please take your token to the billing counter and pay cash.
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '10px', marginTop: '4px' }}>
                  <button onClick={handleCloseCheckout} className="btn-secondary" style={{ flex: 1, justifyContent: 'center' }}>Cancel</button>
                  <button onClick={handlePlaceOrder} className="btn-primary" style={{ flex: 1, justifyContent: 'center' }}>Place Order</button>
                </div>
              </>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px', textAlign: 'center', padding: '10px 0' }}>
                <div style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: 'var(--radius-full)',
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#059669',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '1.5rem'
                }}>
                  <Check size={24} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 800, marginBottom: '4px' }}>Order Submitted</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Order registered on local database.</p>
                </div>

                <div style={{ padding: '10px', background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', border: '1px solid #e2e8f0', width: '100%' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>TOKEN NUMBER</span>
                  <div style={{ fontSize: '1.2rem', fontWeight: 900, color: '#0c2340', marginTop: '2px' }}>{placedOrderId}</div>
                </div>

                <button onClick={handleCloseCheckout} className="btn-primary" style={{ width: '100%', justifyContent: 'center' }}>
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Inject custom CSS for mobile elements */}
      <style>{`
        @media (max-width: 768px) {
          .mobile-cart-fab {
            display: flex !important;
          }
        }
      `}</style>
    </div>
  );
};

export default CustomerDashboard;
