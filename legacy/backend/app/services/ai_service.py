import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from typing import Dict, Any, List

load_dotenv()

class AIService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") # Fallback to openai key if gemini not set, but actually we need gemini key
        if not api_key:
             # Just a warning, might handle gracefully if user hasn't set it yet
             print("Warning: GEMINI_API_KEY not found.")
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
            self.embedding_model = 'models/text-embedding-004'

    async def extract_financial_data(self, image_parts: list) -> Dict[str, Any]:
        """
        Extracts financial data from image parts using Gemini 1.5 Flash.
        Returns a JSON dictionary.
        """
        prompt = """
        Analyze this financial document. Extract the key financial data into a structured JSON format.
        The JSON should have the following structure:
        {
            "title": "Document Title",
            "summary": "Brief summary of the document",
            "tables": [
                {
                    "name": "Table Name (e.g., Balance Sheet)",
                    "headers": ["Col1", "Col2"],
                    "rows": [
                        ["Row1Col1", "Row1Col2"]
                    ]
                }
            ],
            "key_metrics": {
                "metric_name": "value"
            }
        }
        Ensure all numbers are standardized.
        """
        
        try:
            response = self.model.generate_content([prompt, *image_parts])
            return json.loads(response.text)
        except Exception as e:
            print(f"Error extracting data: {e}")
            return {"error": str(e), "raw_text": response.text if 'response' in locals() else ""}

    async def generate_embedding(self, text: str) -> List[float]:
        if not text:
            return [0.0] * 768
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=text[:9000], # Limit content size
                task_type="retrieval_document",
                title="Financial Document"
            )
            return result['embedding']
        except Exception as e:
            print(f"Embedding error: {e}")
            return [0.0] * 768

ai_service = AIService()
