import React, { useState, useRef } from 'react';
import { Mic, MicOff, Volume2 } from 'lucide-react';
import { voiceToText, queryRag } from '../api';

const VoiceInterface = ({ onMessage, onOrder }) => {
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorderRef.current = new MediaRecorder(stream);
            audioChunksRef.current = [];

            mediaRecorderRef.current.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorderRef.current.onstop = async () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
                await processAudio(audioBlob);
            };

            mediaRecorderRef.current.start();
            setIsRecording(true);
        } catch (error) {
            console.error("Error accessing microphone:", error);
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    const processAudio = async (audioBlob) => {
        if (audioBlob.size === 0) {
            onMessage({ text: "No audio recorded. Please hold the button longer.", sender: 'system' });
            return;
        }
        setIsProcessing(true);
        try {
            // 1. Get Text from Voice first
            onMessage({ text: "🎤 Listening...", sender: 'system' });
            const userText = await voiceToText(audioBlob);

            // Show user text appropriately
            onMessage({ text: userText, sender: 'user' });

            // 2. Query AI with the text
            onMessage({ text: "🤖 Thinking...", sender: 'system' });
            const result = await queryRag(userText);

            onMessage({ text: result.aiResponse, sender: 'ai' });

            if (result.audioBase64) {
                playAudio(result.audioBase64);
            }

            if (result.order) {
                onOrder(result.order);
            }
        } catch (error) {
            console.error("Error processing voice query:", error);
            let errMsg = "Error processing request.";
            if (error.response) {
                errMsg += ` Server responded with ${error.response.status}: ${JSON.stringify(error.response.data)}`;
            } else if (error.request) {
                errMsg += " No response from server. Is backend running?";
            } else {
                errMsg += ` ${error.message}`;
            }
            onMessage({ text: errMsg, sender: 'system' });
        } finally {
            setIsProcessing(false);
        }
    };

    const playAudio = (base64Audio) => {
        const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
        audio.play();
    };

    const toggleRecording = async () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    };

    return (
        <div className="voice-controls">
            <button
                className={`mic-button ${isRecording ? 'recording' : ''} ${isProcessing ? 'processing' : ''}`}
                onClick={toggleRecording}
                disabled={isProcessing}
            >
                {isRecording ? <div className="stop-square" /> : <Mic size={32} />}
            </button>
            <div className="status-text">
                {isRecording ? "Listening... (Click to Stop)" : isProcessing ? "Thinking..." : "Tap to Speak"}
            </div>
            {/* Hidden audio element for browser autoplay policies sometimes needing user interaction */}
            <audio id="audio-player" style={{ display: 'none' }} />
        </div>
    );
};

export default VoiceInterface;
