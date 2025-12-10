import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

export const voiceToText = async (audioBlob) => {
    const formData = new FormData();
    formData.append('file', audioBlob, 'voice_query.wav');

    const response = await axios.post(`${API_BASE_URL}/stt`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data.text;
};

export const queryRag = async (text) => {
    const response = await axios.post(`${API_BASE_URL}/rag-query`, { text });
    return {
        aiResponse: response.data.response_text,
        audioBase64: response.data.audio_base64,
        order: response.data.order
    };
};

// Deprecated wrapper kept for compatibility if needed, but not used in optimized flow
export const voiceQuery = async (audioBlob) => {
    const text = await voiceToText(audioBlob);
    const result = await queryRag(text);
    return {
        userText: text,
        ...result
    };
};
