import React, { useRef, useEffect } from 'react';

const ChatInterface = ({ messages }) => {
    const chatEndRef = useRef(null);

    const scrollToBottom = () => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    return (
        <div className="chat-container">
            {messages.map((msg, index) => (
                <div key={index} className={`message ${msg.sender}`}>
                    <div className="message-content">
                        {msg.text}
                    </div>
                </div>
            ))}
            <div ref={chatEndRef} />
        </div>
    );
};

export default ChatInterface;
