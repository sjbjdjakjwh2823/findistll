
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, validator

class RawDocument(BaseModel):
    id: UUID
    source: Literal['sec_10k', 'fred', 'finnhub', 'fmp']
    ticker: Optional[str] = None
    document_type: str
    raw_content: Dict[str, Any]  # Assuming JSONB maps to a Python dict
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    processing_status: Literal['pending', 'processed', 'failed'] = 'pending'

    @validator('ticker', always=True)
    def validate_ticker_for_financial_sources(cls, v, values):
        if values.get('source') in ['sec_10k', 'finnhub', 'fmp'] and not v:
            raise ValueError('Ticker is required for financial document sources.')
        return v

class GeneratedSample(BaseModel):
    id: UUID
    raw_document_id: UUID
    template_type: Literal['qa_pair', 'reasoning_chain', 'summary', 'risk_analysis', 'metrics_extraction']
    generated_content: Dict[str, Any] # Assuming JSONB maps to a Python dict
    model_used: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class HumanAnnotation(BaseModel):
    id: UUID
    sample_id: UUID
    annotator_id: UUID
    action: Literal['approved', 'corrected', 'rejected']
    corrections: Optional[Dict[str, Any]] = None # JSONB, can be empty
    reasoning: Optional[str] = None
    annotated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('corrections', always=True)
    def corrections_must_be_present_if_corrected(cls, v, values):
        if values.get('action') == 'corrected' and not v:
            raise ValueError('Corrections must be provided if the action is "corrected".')
        if values.get('action') == 'approved' and v:
            raise ValueError('Corrections should be empty if the action is "approved".')
        return v

class GoldenDataset(BaseModel):
    id: UUID
    version: str
    dataset_type: Literal['finetune', 'evaluation', 'rag_corpus']
    sample_count: int = Field(..., ge=0)
    quality_metrics: Dict[str, Any] # JSONB
    published_at: datetime = Field(default_factory=datetime.utcnow)
    huggingface_path: Optional[str] = None

class QAPipeline:
    def __init__(self):
        self.validators = {
            "raw_document": RawDocument,
            "generated_sample": GeneratedSample,
            "human_annotation": HumanAnnotation,
            "golden_dataset": GoldenDataset
        }

    def validate_data(self, data: Dict[str, Any], data_type: str) -> Dict[str, Any]:
        validator_model = self.validators.get(data_type)
        if not validator_model:
            raise ValueError(f"No validator found for data type: {data_type}")
        try:
            validated_data = validator_model(**data)
            print(f"Validation successful for {data_type} with ID: {data.get('id')}")
            return validated_data.dict() # Return dict for easier integration
        except ValidationError as e:
            print(f"Validation failed for {data_type} with ID: {data.get('id')}: {e.json()}")
            raise e

    def run_consistency_checks(self, data_list: List[Dict[str, Any]], data_type: str) -> List[Dict[str, Any]]:
        """
        Runs consistency checks across a list of data entries.
        For now, this mainly leverages Pydantic's internal validators,
        but can be extended for cross-record consistency.
        """
        print(f"Running consistency checks for {data_type}...")
        validated_list = []
        for item in data_list:
            try:
                validated_list.append(self.validate_data(item, data_type))
            except ValidationError as e:
                print(f"Consistency check failed for an item in {data_type}: {e.json()}")
                # Depending on requirement, either raise or continue and log errors
                # For now, we'll re-raise to indicate a failure in the batch
                raise e
        print(f"Consistency checks completed successfully for {data_type}.")
        return validated_list

    def run_statistical_validation(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Performs basic statistical validation on generated samples.
        e.g., checks distribution of confidence scores.
        """
        if not samples:
            return {"status": "skipped", "reason": "No samples provided for statistical validation."}

        confidence_scores = [s['confidence_score'] for s in samples if 'confidence_score' in s]
        
        if not confidence_scores:
            return {"status": "warning", "message": "No confidence scores found in samples."}

        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        
        # Simple check: warn if average confidence is too low
        if avg_confidence < 0.5:
            print(f"Warning: Average confidence score is low ({avg_confidence:.2f}).")

        # More advanced statistical checks can be added here (e.g., outlier detection, distribution analysis)
        
        stats = {
            "avg_confidence_score": avg_confidence,
            "min_confidence_score": min(confidence_scores),
            "max_confidence_score": max(confidence_scores),
            "total_samples_with_scores": len(confidence_scores)
        }
        print(f"Statistical validation completed: {stats}")
        return {"status": "success", "metrics": stats}

# Example Usage (for testing the module)
if __name__ == "__main__":
    qa_pipeline = QAPipeline()

    # --- Test RawDocument Validation ---
    print("\n--- Testing RawDocument Validation ---")
    valid_raw_doc_data = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "source": "sec_10k",
        "ticker": "AAPL",
        "document_type": "10-K Filing",
        "raw_content": {"filing_date": "2025-01-01", "report_text": "..."}
    }
    try:
        qa_pipeline.validate_data(valid_raw_doc_data, "raw_document")
    except ValidationError:
        pass # Expected to pass

    invalid_raw_doc_data_no_ticker = {
        "id": "123e4567-e89b-12d3-a456-426614174001",
        "source": "finnhub",
        "document_type": "Earnings Report",
        "raw_content": {"q1_2024": "..."}
    }
    try:
        qa_pipeline.validate_data(invalid_raw_doc_data_no_ticker, "raw_document")
    except ValidationError:
        print("Caught expected validation error for RawDocument (missing ticker).")

    # --- Test GeneratedSample Validation ---
    print("\n--- Testing GeneratedSample Validation ---")
    valid_generated_sample_data = {
        "id": "a23e4567-e89b-12d3-a456-426614174000",
        "raw_document_id": "123e4567-e89b-12d3-a456-426614174000",
        "template_type": "qa_pair",
        "generated_content": {"question": "What is AAPL revenue?", "answer": "100B"},
        "model_used": "GPT-4",
        "confidence_score": 0.95
    }
    try:
        qa_pipeline.validate_data(valid_generated_sample_data, "generated_sample")
    except ValidationError:
        pass # Expected to pass

    invalid_generated_sample_data_confidence = {
        "id": "a23e4567-e89b-12d3-a456-426614174001",
        "raw_document_id": "123e4567-e89b-12d3-a456-426614174000",
        "template_type": "summary",
        "generated_content": {"summary": "..."},
        "model_used": "Gemini-Pro",
        "confidence_score": 1.1 # Invalid score
    }
    try:
        qa_pipeline.validate_data(invalid_generated_sample_data_confidence, "generated_sample")
    except ValidationError:
        print("Caught expected validation error for GeneratedSample (invalid confidence).")

    # --- Test HumanAnnotation Validation ---
    print("\n--- Testing HumanAnnotation Validation ---")
    valid_annotation_approved = {
        "id": "b23e4567-e89b-12d3-a456-426614174000",
        "sample_id": "a23e4567-e89b-12d3-a456-426614174000",
        "annotator_id": "c23e4567-e89b-12d3-a456-426614174000",
        "action": "approved",
        "corrections": None
    }
    try:
        qa_pipeline.validate_data(valid_annotation_approved, "human_annotation")
    except ValidationError:
        pass # Expected to pass

    valid_annotation_corrected = {
        "id": "b23e4567-e89b-12d3-a456-426614174001",
        "sample_id": "a23e4567-e89b-12d3-a456-426614174000",
        "annotator_id": "c23e4567-e89b-12d3-a456-426614174000",
        "action": "corrected",
        "corrections": {"old_answer": "100B", "new_answer": "105B"},
        "reasoning": "Updated revenue figure from Q3 report."
    }
    try:
        qa_pipeline.validate_data(valid_annotation_corrected, "human_annotation")
    except ValidationError:
        pass # Expected to pass

    invalid_annotation_corrected_no_corrections = {
        "id": "b23e4567-e89b-12d3-a456-426614174002",
        "sample_id": "a23e4567-e89b-12d3-a456-426614174000",
        "annotator_id": "c23e4567-e89b-12d3-a456-426614174000",
        "action": "corrected",
        "corrections": None
    }
    try:
        qa_pipeline.validate_data(invalid_annotation_corrected_no_corrections, "human_annotation")
    except ValidationError:
        print("Caught expected validation error for HumanAnnotation (corrected without corrections).")

    # --- Test Statistical Validation ---
    print("\n--- Testing Statistical Validation ---")
    test_samples = [
        {"id": "s1", "confidence_score": 0.8},
        {"id": "s2", "confidence_score": 0.9},
        {"id": "s3", "confidence_score": 0.75},
        {"id": "s4", "confidence_score": 0.2}, # Low score
        {"id": "s5", "confidence_score": 0.88},
    ]
    # For statistical validation, we're not using the full GeneratedSample model,
    # just extracting confidence_score. We will mock the required fields for the function.
    mock_generated_samples_for_stats = [
        {**valid_generated_sample_data, "id": UUID("e0a7e171-4680-49c0-9b6f-77e812d3a456"), "confidence_score": 0.8},
        {**valid_generated_sample_data, "id": UUID("f0a7e171-4680-49c0-9b6f-77e812d3a456"), "confidence_score": 0.9},
        {**valid_generated_sample_data, "id": UUID("d1a7e171-4680-49c0-9b6f-77e812d3a456"), "confidence_score": 0.75},
        {**valid_generated_sample_data, "id": UUID("c2a7e171-4680-49c0-9b6f-77e812d3a456"), "confidence_score": 0.2},
        {**valid_generated_sample_data, "id": UUID("b3a7e171-4680-49c0-9b6f-77e812d3a456"), "confidence_score": 0.88},
    ]
    qa_pipeline.run_statistical_validation(mock_generated_samples_for_stats)
