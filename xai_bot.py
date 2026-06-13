import os
import logging
from typing import List, Dict, Any, Optional
import ollama

logger = logging.getLogger(__name__)

class OllamaSupportBot:
    def __init__(self, model_id: str = "llama3.2"):
        logger.info(f"🔄 Initializing Ollama Bot with model: {model_id}...")
        self.model_id = model_id
        self.client = ollama.AsyncClient()
        
        # Verify connection and pull model if needed
        # We handle this in get_response to keep init fast and avoid startup hangs
        self.docs_context = self._load_docs()

    def _load_docs(self) -> str:
        docs_files = ['README.md', 'ARCHITECTURE.md', 'QUICK_REFERENCE.md', 'INTEGRATION_GUIDE.md']
        context = "Project Documentation Summary:\n"
        for file in docs_files:
            if os.path.exists(file):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        context += f"- {file}: {f.read()[:500]}...\n"
                except: pass
        return context

    async def get_response(self, message: str, ticker: Optional[str] = None, analysis_context: Optional[Dict[str, Any]] = None) -> str:
        system_prompt = f"You are a professional stock analyst for the Nifty 50. Use the following context to answer questions about the project or stocks: {self.docs_context}"
        
        if ticker and analysis_context:
            user_input = f"Ticker: {ticker}\nAnalysis: {analysis_context}\nQuestion: {message}"
        else:
            user_input = message

        try:
            response = await self.client.chat(model=self.model_id, messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_input},
            ])
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama Error: {e}")
            # Try to pull model if it doesn't exist
            if "not found" in str(e).lower():
                logger.info(f"Model {self.model_id} not found. Attempting to pull...")
                try:
                    await self.client.pull(self.model_id)
                    return "I was just setting up my brain (pulling the model). Please try asking again in a moment!"
                except: pass
            raise

class CloudSupportBot:
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
        bot_mode = os.getenv("CHATBOT_MODE", "ollama").lower() 
        api_key = os.getenv("GEMINI_API_KEY")
        
        if bot_mode == "cloud" and api_key:
            _bot_instance = CloudSupportBot(api_key)
        else:
            try:
                _bot_instance = OllamaSupportBot()
                logger.info("✅ Ollama Bot ready.")
            except Exception as e:
                logger.warning(f"Failed to load Ollama bot, checking for cloud fallback: {e}")
                if api_key:
                    _bot_instance = CloudSupportBot(api_key)
                else:
                    logger.error("No valid chatbot configuration found.")
                    return None
    return _bot_instance
