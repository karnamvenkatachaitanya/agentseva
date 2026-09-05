import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class HuggingFaceAIService:
    """
    AI Service connected to Hugging Face Inference API.
    Supports Open-Source LLMs (e.g. Qwen/Qwen2.5-7B-Instruct, Llama-3.2, Mistral-7B)
    with smart fallback for Kirana Store assistance.
    """

    def __init__(self):
        self.api_key = settings.HUGGINGFACE_API_KEY or os.environ.get("HUGGINGFACE_API_KEY", "")
        self.model_id = settings.HF_LLM_MODEL or "Qwen/Qwen2.5-7B-Instruct"

    def chat_completion(self, user_message: str, history: Optional[List[Dict[str, str]]] = None, context_products: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Generates response using Hugging Face Inference API.
        Falls back to local Kirana rule-engine if HF key is missing or request fails.
        """
        if self.api_key and self.api_key.strip():
            try:
                hf_response = self._call_hf_inference_api(user_message, history, context_products)
                if hf_response:
                    return {
                        "status": "success",
                        "source": f"huggingface ({self.model_id})",
                        "response": hf_response
                    }
            except Exception as e:
                logger.warning(f"Hugging Face API call failed: {e}. Falling back to Kirana Rule Engine.")

        # Fallback Engine
        fallback_text = self._generate_fallback_response(user_message, context_products)
        return {
            "status": "success",
            "source": "kirana_local_assistant (fallback)",
            "response": fallback_text
        }

    def _call_hf_inference_api(self, message: str, history: Optional[List[Dict[str, str]]] = None, context_products: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
        """Call HF Router / Serverless Inference endpoint"""
        url = f"https://api-inference.huggingface.co/models/{self.model_id}"
        
        system_prompt = (
            "You are Agent Seva, a helpful, polite Kirana store voice assistant in India. "
            "Help customers find items, check prices, recommend products, and answer store questions in English and Hindi/Hinglish."
        )
        if context_products:
            product_names = [p.get('name') for p in context_products[:10] if isinstance(p, dict)]
            system_prompt += f" Available Kirana products: {', '.join(product_names)}."

        full_prompt = f"System: {system_prompt}\nUser: {message}\nAssistant:"
        payload = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": 200,
                "temperature": 0.7,
                "return_full_text": False
            }
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if isinstance(result, list) and len(result) > 0:
                return result[0].get("generated_text", "").strip()
            elif isinstance(result, dict) and "generated_text" in result:
                return result["generated_text"].strip()
        return None

    def _generate_fallback_response(self, text: str, context_products: Optional[List[Dict[str, Any]]] = None) -> str:
        """Smart fallback response generator for Kirana store inquiries."""
        query = text.lower()
        
        if any(w in query for w in ["milk", "dahi", "paneer", "butter", "cheese", "curd"]):
            return "Namaste! We have fresh Amul Taaza Milk (₹54/L), Amul Fresh Paneer (200g @ ₹95), Amul Salted Butter (₹58), and Amul Masti Dahi in stock at Aisle 3A (Refrigerated)."
        elif any(w in query for w in ["atta", "rice", "basmati", "dal", "toor", "moong", "rajma", "chana"]):
            return "We have premium Aashirvaad Chakki Atta (10kg @ ₹430), India Gate Basmati Rice (5kg @ ₹490), and Tata Sampann Unpolished Toor Dal (1kg @ ₹170) at Aisles 4A & 4B."
        elif any(w in query for w in ["oil", "ghee", "mustard"]):
            return "Our top seller is Fortune Sunlite Sunflower Oil (1L @ ₹145) and Amul Pure Cow Ghee (1L Tin @ ₹650) located at Aisle 2A."
        elif any(w in query for w in ["biscuit", "chips", "maggi", "snack"]):
            return "Check out Parle-G Family Pack (800g @ ₹90), Maggi 2-Minute Noodles (12-pack @ ₹168), and Lay's Magic Masala (90g @ ₹30) in Aisles 1A & 1C."
        elif any(w in query for w in ["tea", "chai", "coffee", "juice"]):
            return "We stock Red Label Tea (1kg @ ₹520), Nescafe Classic Coffee (100g @ ₹340), and Real Fruit Power Juice (1L @ ₹110) at Aisles 2B & 3C."
        elif "checkout" in query or "pay" in query or "bill" in query:
            return "You can proceed to checkout by clicking the Shopping Cart button. We support UPI QR Code, Cash, and Assisted Counter payments!"
        else:
            return f"Namaste! I searched our Kirana catalog for '{text}'. How else can I assist you with your grocery order today?"

hf_ai_service = HuggingFaceAIService()
