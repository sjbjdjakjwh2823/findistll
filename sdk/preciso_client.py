import requests
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class PrecisoClient:
    """
    Python SDK for Preciso B2B Financial AI Toolkit.
    """

    def __init__(self, base_url: str = "https://api.preciso-data.com", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["X-Preciso-API-Key"] = api_key

    def create_case(self, title: str) -> str:
        """Create a new institutional case."""
        url = f"{self.base_url}/cases"
        payload = {"title": title}
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()["case_id"]

    def add_document(self, case_id: str, filename: str, content: str, source: str = "sdk") -> str:
        """Add a document to an existing case."""
        url = f"{self.base_url}/cases/{case_id}/documents"
        payload = {
            "doc_id": f"doc_{filename}_{case_id[:8]}",
            "case_id": case_id,
            "filename": filename,
            "content": content,
            "source": source
        }
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()["doc_id"]

    def distill(self, case_id: str) -> Dict[str, Any]:
        """Run FinDistill engine to extract facts and CoT."""
        url = f"{self.base_url}/cases/{case_id}/distill"
        response = requests.post(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def decide(self, case_id: str) -> Dict[str, Any]:
        """Run FinRobot engine to generate an institutional decision."""
        url = f"{self.base_url}/cases/{case_id}/decide"
        response = requests.post(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def verify_integrity(self, case_id: str) -> Dict[str, Any]:
        """Verify data integrity using Zero-Knowledge Proof (ZKP)."""
        url = f"{self.base_url}/zkp/verify/{case_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def run_full_pipeline(self, title: str, filename: str, content: str) -> Dict[str, Any]:
        """Execute the complete Palantir-style intelligence pipeline."""
        case_id = self.create_case(title)
        self.add_document(case_id, filename, content)
        distill_data = self.distill(case_id)
        decision_data = self.decide(case_id)
        zkp_data = self.verify_integrity(case_id)
        
        return {
            "case_id": case_id,
            "distill": distill_data,
            "decision": decision_data,
            "integrity": zkp_data
        }

if __name__ == "__main__":
    # Example usage
    client = PrecisoClient(base_url="http://localhost:8000")
    print("Preciso SDK Initialized.")
