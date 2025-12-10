import React from 'react';
import { X, Check } from 'lucide-react';

const OrderModal = ({ order, isOpen, onClose, onConfirm }) => {
    if (!isOpen || !order) return null;

    return (
        <div className="modal-overlay">
            <div className="modal-content">
                <div className="modal-header">
                    <h2>Confirm Your Order</h2>
                    <button onClick={onClose} className="close-btn"><X /></button>
                </div>

                <div className="order-items">
                    {order.items.map((item, index) => (
                        <div key={index} className="order-item">
                            <div className="item-details">
                                <span className="item-qty">{item.quantity}x</span>
                                <span className="item-name">{item.item}</span>
                            </div>
                            {item.customization && <div className="item-cust">Note: {item.customization}</div>}
                            {item.spice_level && <div className="item-spice">Spice: {item.spice_level}</div>}
                        </div>
                    ))}
                </div>

                <div className="modal-actions">
                    <button onClick={onClose} className="cancel-btn">Cancel</button>
                    <button onClick={onConfirm} className="confirm-btn">
                        <Check size={18} /> Confirm Order
                    </button>
                </div>
            </div>
        </div>
    );
};

export default OrderModal;
