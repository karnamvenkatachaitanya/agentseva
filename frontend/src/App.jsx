import React, { useState } from 'react';
import ChatInterface from './components/ChatInterface';
import VoiceInterface from './components/VoiceInterface';
import OrderModal from './components/OrderModal';
import { ChefHat } from 'lucide-react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    { text: "Hi! I'm your AI Waiter. What can I get for you today?", sender: 'ai' }
  ]);
  const [currentOrder, setCurrentOrder] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleMessage = (msg) => {
    setMessages(prev => [...prev, msg]);
  };

  const handleOrder = (order) => {
    setCurrentOrder(order);
    setIsModalOpen(true);
  };

  const confirmOrder = () => {
    handleMessage({ text: "Order confirmed! Sending to kitchen.", sender: 'system' });
    setIsModalOpen(false);
    setCurrentOrder(null);
    // Here you would typically send a confirmation API call
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <ChefHat size={32} />
        <h1>Future AI</h1>
      </header>

      <main className="main-content">
        <ChatInterface messages={messages} />
      </main>

      <footer className="app-footer">
        <VoiceInterface onMessage={handleMessage} onOrder={handleOrder} />
      </footer>

      <OrderModal
        order={currentOrder}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onConfirm={confirmOrder}
      />
    </div>
  );
}

export default App;
