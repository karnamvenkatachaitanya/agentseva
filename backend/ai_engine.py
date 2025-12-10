import json
import os
from typing import List, Dict, Any
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import OllamaLLM
from backend.models import Order

# Initialize Embedding Model
# using a small, fast model for prototype
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
PERSIST_DIRECTORY = "data/chroma_db"

class AIEngine:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        self.vector_store = None
        self.retriever = None
        self.llm = OllamaLLM(model="qwen2.5:1.5b") # Assumes qwen2.5:1.5b is pulled in Ollama
        
        # Load or Create Vector Store
        if os.path.exists(PERSIST_DIRECTORY) and os.listdir(PERSIST_DIRECTORY):
             self.vector_store = Chroma(persist_directory=PERSIST_DIRECTORY, embedding_function=self.embeddings)
        else:
            self._build_vector_store()
            
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
        self.chain = self._build_chain()

    def _build_vector_store(self):
        print("Building Vector Store from menu.json...")
        with open("data/menu.json", "r") as f:
            menu_data = json.load(f)
        
        documents = []
        for category, items in menu_data["categories"].items():
            for item in items:
                content = f"Item: {item['name']}. Category: {category}. Price: {item['price']}. Description: {item['desc']}. Spice Level: {item['spice']}. Allergens: {', '.join(item['allergens'])}."
                meta = {"name": item["name"], "price": item["price"], "category": category}
                documents.append(Document(page_content=content, metadata=meta))
        
        self.vector_store = Chroma.from_documents(
            documents=documents, 
            embedding=self.embeddings, 
            persist_directory=PERSIST_DIRECTORY
        )
        print("Vector Store created.")

    def _build_chain(self):
        template = """
        You are an AI Waiter.
        Menu Context:
        {context}
        
        Customer: {question}
        
        Task:
        1. Answer based on menu. If unknown, say "I don't know".
        2. Create a JSON order if applicable.
        
        output strictly valid JSON:
        {{
            "response_text": "Your verbal response here",
            "order": {{
                "items": [
                    {{
                        "item": "Exact Item Name",
                        "quantity": 1,
                        "customization": "notes",
                        "spice_level": "Low/Medium/High",
                        "addons": []
                    }}
                ],
                "total_price": 0
            }}
        }}
        
        If no order, "order" is null.
        IMPORTANT: Output ONLY JSON. No markdown ```json``` tags.
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["context", "question"]
        )
        
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        def parse_output(text):
            # Custom robust parsing for chatty models
            import json
            import re
            try:
                # Try to find JSON object in text
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    return json.loads(match.group())
                return json.loads(text)
            except:
                return {
                    "response_text": text,
                    "order": None
                }

        rag_chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | parse_output 
        )
        
        return rag_chain

    def query(self, text: str) -> Dict[str, Any]:
        try:
            response = self.chain.invoke(text)
            return response
        except Exception as e:
            print(f"Error during RAG query: {e}")
            return {
                "response_text": "I'm having trouble understanding the menu right now. Please try again.",
                "order": None
            }

# Lazy initialization - create on first use to avoid import-time errors
_ai_engine_instance = None

def get_ai_engine():
    global _ai_engine_instance
    if _ai_engine_instance is None:
        _ai_engine_instance = AIEngine()
    return _ai_engine_instance

# For backward compatibility, expose ai_engine as a lazy-loaded property
class LazyAIEngine:
    def __getattr__(self, name):
        engine = get_ai_engine()
        return getattr(engine, name)

ai_engine = LazyAIEngine()
