import os
import logging
from typing import List, Dict, Any, Optional
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

logger = logging.getLogger(__name__)

class LocalSupportBot:
    def __init__(self, model_id: str = "microsoft/Phi-3-mini-4k-instruct"):
        logger.info(f"🔄 Initializing Local Bot with model: {model_id}...")
        self.model_id = model_id
        
        # Determine device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            
            # Load model with optimizations for RTX 4050 (6GB VRAM)
            # Using 4-bit quantization if possible, else half precision
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                device_map="auto",
                torch_dtype="auto",
                trust_remote_code=True,
                # load_in_4bit=True # Optional: Requires bitsandbytes
            )
            
            self.pipe = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
            )
            
            logger.info(f"✅ Local Bot initialized successfully on {self.device}!")
        except Exception as e:
            logger.error(f"❌ Failed to initialize local model: {e}")
            raise

        self.docs_context = self._load_docs()

    def _load_docs(self) -> str:
        docs_files = ['README.md', 'ARCHITECTURE.md', 'QUICK_REFERENCE.md', 'INTEGRATION_GUIDE.md']
        context = "Project Documentation:\n"
        for file in docs_files:
            if os.path.exists(file):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        context += f"File {file}:\n{f.read()[:500]}...\n" # Truncate for local LLM context window
                except: pass
        return context

    async def get_response(self, message: str, ticker: Optional[str] = None, analysis_context: Optional[Dict[str, Any]] = None) -> str:
        system_prompt = f"You are a professional stock analyst for the Nifty 50. Use the following project context if needed: {self.docs_context}"
        
        if ticker and analysis_context:
            user_input = f"Ticker: {ticker}\nContext: {analysis_context}\nQuestion: {message}"
        else:
            user_input = message

        # Format for Phi-3 Instruct
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        try:
            outputs = self.pipe(
                prompt,
                max_new_tokens=256,
                do_sample=True,
                temperature=0.2,
                top_k=50,
                top_p=0.95
            )
            response = outputs[0]["generated_text"]
            # Extract only the assistant's part
            if "<|assistant|>" in response:
                response = response.split("<|assistant|>")[-1].strip()
            return response
        except Exception as e:
            logger.error(f"Local LLM Error: {e}")
            return f"I'm sorry, I encountered a local processing error: {str(e)}"

class CloudSupportBot:
    # Existing Gemini implementation
    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model_name = 'gemini-1.5-flash'
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"✅ Cloud Bot initialized with model: {self.model_name}")
        self.docs_context = self._load_docs()

    def _load_docs(self) -> str:
        docs_files = ['README.md', 'ARCHITECTURE.md', 'QUICK_REFERENCE.md', 'INTEGRATION_GUIDE.md']
        context = ""
        for file in docs_files:
            if os.path.exists(file):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        context += f"--- {file} ---\n{f.read()}\n\n"
                except: pass
        return context

    async def get_response(self, message: str, ticker: Optional[str] = None, analysis_context: Optional[Dict[str, Any]] = None) -> str:
        system_prompt = f"You are the Nifty 50 RL Analytical Assistant. Tone: professional, objective. {self.docs_context}"
        if ticker and analysis_context:
            full_prompt = f"{system_prompt}\n\nDATA FOR {ticker}: {analysis_context}\nUSER QUERY: {message}"
        else:
            full_prompt = f"{system_prompt}\nUSER QUERY: {message}"

        try:
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Cloud API Error: {e}")
            return f"I'm sorry, I encountered a cloud processing error: {str(e)}"

# Singleton instance
_bot_instance = None

def get_bot():
    global _bot_instance
    if _bot_instance is None:
        # Check for mode
        bot_mode = os.getenv("CHATBOT_MODE", "local").lower() # Default to local now
        api_key = os.getenv("GEMINI_API_KEY")
        
        if bot_mode == "cloud" and api_key:
            _bot_instance = CloudSupportBot(api_key)
        else:
            try:
                _bot_instance = LocalSupportBot()
            except Exception as e:
                logger.warning(f"Failed to load local bot, checking for cloud fallback: {e}")
                if api_key:
                    _bot_instance = CloudSupportBot(api_key)
                else:
                    logger.error("No valid chatbot configuration found (no API key and local model failed).")
                    return None
    return _bot_instance
