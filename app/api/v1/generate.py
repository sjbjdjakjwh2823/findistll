"""
DataForge Generate API - Phase 1
LLM Template-based sample generation pipeline.
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["DataForge - Generate"])


# =============================================================================
# Models
# =============================================================================

class GenerateRequest(BaseModel):
    """Request model for sample generation."""
    document_id: str = Field(..., description="Raw document ID to generate from")
    template_type: str = Field(..., description="Template type: 'qa_pair', 'reasoning_chain', 'summary', 'risk_analysis', 'metrics_extraction'")
    model: str = Field("gpt-4", description="Model to use for generation")
    temperature: float = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int = Field(2000, ge=100, le=8000, description="Max output tokens")


class GenerateResponse(BaseModel):
    """Response model for generation."""
    sample_id: str
    status: str
    template_type: str
    generated_content: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    generation_time_ms: Optional[int] = None
    message: Optional[str] = None


class BatchGenerateRequest(BaseModel):
    """Request for batch generation."""
    document_ids: List[str] = Field(..., description="List of document IDs")
    template_types: List[str] = Field(..., description="Template types to generate")
    model: str = Field("gpt-4", description="Model to use")


class BatchGenerateResponse(BaseModel):
    """Response for batch generation."""
    job_id: str
    status: str
    total_tasks: int
    message: str


class SelfInstructRequest(BaseModel):
    """Request for Self-Instruct data augmentation."""
    target_count: int = Field(10, ge=1, le=100, description="Number of augmented cases")


class EvalRunRequest(BaseModel):
    """Run a lightweight evaluation against gold standard cases."""
    limit: int = Field(50, ge=1, le=200)


class TemplateResponse(BaseModel):
    """Response model for template listing."""
    templates: List[Dict[str, Any]]


class SampleListResponse(BaseModel):
    """Response for sample listing."""
    samples: List[Dict[str, Any]]
    total: int
    offset: int
    limit: int


# =============================================================================
# Database Functions
# =============================================================================

def get_db():
    """Get database client."""
    from app.db.supabase_db import SupabaseDB
    from app.core.config import load_settings
    
    settings = load_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    return SupabaseDB(settings.supabase_url, settings.supabase_service_role_key)


def get_document_by_id(db, doc_id: str) -> Optional[Dict[str, Any]]:
    """Get a single document by ID."""
    result = db.client.table("raw_documents").select("*").eq("id", doc_id).execute()
    return result.data[0] if result.data else None


def get_active_template(db, template_type: str) -> Optional[Dict[str, Any]]:
    """Get the active prompt template for a type."""
    result = db.client.table("prompt_templates").select("*").eq("template_type", template_type).eq("is_active", True).execute()
    return result.data[0] if result.data else None


def get_all_templates(db) -> List[Dict[str, Any]]:
    """Get all prompt templates."""
    result = db.client.table("prompt_templates").select("*").order("template_type").execute()
    return result.data or []


def insert_generated_sample(db, sample_data: Dict[str, Any]) -> str:
    """Insert a generated sample."""
    sample_id = str(uuid4())
    
    payload = {
        "id": sample_id,
        "raw_document_id": sample_data["raw_document_id"],
        "template_type": sample_data["template_type"],
        "template_version": sample_data.get("template_version", "v1"),
        "generated_content": sample_data["generated_content"],
        "model_used": sample_data["model_used"],
        "model_params": sample_data.get("model_params", {}),
        "confidence_score": sample_data.get("confidence_score"),
        "token_usage": sample_data.get("token_usage", {}),
        "generation_time_ms": sample_data.get("generation_time_ms"),
        "review_status": "pending",
        "priority_score": calculate_priority(sample_data)
    }
    
    db.client.table("generated_samples").insert(payload).execute()
    return sample_id


def get_samples(
    db,
    template_type: Optional[str] = None,
    review_status: Optional[str] = None,
    offset: int = 0,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Query generated samples with filters."""
    query = db.client.table("generated_samples").select("*, raw_documents(source, ticker, document_type)")
    
    if template_type:
        query = query.eq("template_type", template_type)
    if review_status:
        query = query.eq("review_status", review_status)
    
    query = query.order("created_at", desc=True)
    query = query.range(offset, offset + limit - 1)
    
    result = query.execute()
    return result.data or []


def get_sample_by_id(db, sample_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific sample by ID."""
    result = db.client.table("generated_samples").select("*, raw_documents(source, ticker, document_type, raw_content)").eq("id", sample_id).execute()
    return result.data[0] if result.data else None


def get_seed_cases(db, limit: int = 10) -> List[Dict[str, Any]]:
    res = (
        db.client.table("gold_standard_cases")
        .select("*")
        .eq("use_for_training", True)
        .order("validation_score", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def calculate_priority(sample_data: Dict[str, Any]) -> float:
    """Calculate priority score for HITL review queue."""
    priority = 0.5
    
    # Lower confidence = higher priority (needs more review)
    confidence = sample_data.get("confidence_score", 0.5)
    if confidence:
        priority += (1 - confidence) * 0.3
    
    # Certain template types may have higher priority
    high_priority_types = ["risk_analysis", "reasoning_chain"]
    if sample_data.get("template_type") in high_priority_types:
        priority += 0.1
    
    return min(1.0, priority)


# =============================================================================
# LLM Integration
# =============================================================================

async def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    base_url_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Call LLM API (OpenAI or Gemini).
    """
    from app.services.policy_engine import PolicyEngine
    from app.services.anonymizer import redact_sensitive
    from app.services.audit_logger import AuditLogger, AuditEntry
    from app.db.registry import get_db

    # Resolve default model from registry if not provided.
    if not model or str(model).strip().lower() in {"default", "auto"}:
        try:
            db = get_db()
            models = db.list_model_registry(limit=50)
            default = next((m for m in models if m.get("is_default")), None)
            if default:
                model = default.get("model") or default.get("name")
                if not base_url_override:
                    base_url_override = default.get("base_url")
        except Exception as exc:
            logger.warning("Default model lookup failed", exc_info=exc)

    model = model or os.getenv("LOCAL_LLM_MODEL") or "gpt-4"

    openai_key = api_key_override or os.getenv("OPENAI_API_KEY")
    openai_base_url = base_url_override or os.getenv("OPENAI_BASE_URL")
    gemini_key = os.getenv("GEMINI_API_KEY")
    allow_gemini = os.getenv("GEMINI_ENABLED", "0") == "1"

    def _is_local_url(url: Optional[str]) -> bool:
        if not url:
            return False
        host = urlparse(url).hostname or ""
        return host in {"localhost", "127.0.0.1"}

    is_external = False
    if "gemini" in (model or "").lower():
        is_external = True
    elif openai_base_url:
        is_external = not _is_local_url(openai_base_url)
    elif openai_key:
        is_external = True

    policy_engine = PolicyEngine()
    decision = policy_engine.check_egress(
        f"{system_prompt}\n\n{user_prompt}",
        metadata={"channel": "generate", "model": model},
        destination="llm",
    )

    if is_external and decision.action == "block":
        try:
            AuditLogger(get_db()).append_log(
                AuditEntry(
                    action="EGRESS_BLOCKED",
                    actor_type="system",
                    actor_id=None,
                    entity_type="llm_request",
                    entity_id=str(uuid4()),
                    context={"reason": decision.reason, "model": model},
                    outcome={"sensitive_hits": decision.sensitive_hits},
                )
            )
        except Exception as exc:
            logger.warning("Audit log write failed", exc_info=exc)
        raise HTTPException(status_code=403, detail=f"Egress blocked: {decision.reason}")

    if is_external and decision.action == "anonymize":
        system_prompt = redact_sensitive(system_prompt)
        user_prompt = redact_sensitive(user_prompt)

    start_time = time.time()
    
    if ((openai_key or openai_base_url) and "gemini" not in model.lower()):
        result = await _call_openai(system_prompt, user_prompt, model, temperature, max_tokens, openai_key, openai_base_url)
    elif "gemini" in model.lower() and gemini_key and allow_gemini:
        result = await _call_gemini(system_prompt, user_prompt, model, temperature, max_tokens, gemini_key)
    else:
        # Fallback to mock for development
        result = _mock_llm_response(system_prompt, user_prompt)
    
    result["generation_time_ms"] = int((time.time() - start_time) * 1000)
    return result


async def _call_openai(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    api_key: str,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Call OpenAI API."""
    try:
        import openai
        
        client = openai.AsyncOpenAI(
            api_key=api_key or "local-dev-key",
            base_url=(base_url or os.getenv("OPENAI_BASE_URL") or None),
        )
        
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"} if "json" in user_prompt.lower() else None
        )
        
        content = response.choices[0].message.content
        
        # Try to parse as JSON
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError:
            parsed_content = {"raw_text": content}
        
        return {
            "content": parsed_content,
            "token_usage": {
                "input": response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
                "total": response.usage.total_tokens
            },
            "model": response.model,
            "confidence_score": _estimate_confidence(content)
        }
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")


async def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    api_key: str
) -> Dict[str, Any]:
    """Call Google Gemini API."""
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        
        model_instance = genai.GenerativeModel(
            model_name=model if "gemini" in model else "gemini-pro",
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens
            },
            system_instruction=system_prompt
        )
        
        response = await asyncio.to_thread(
            model_instance.generate_content,
            user_prompt
        )
        
        content = response.text
        
        # Try to parse as JSON
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', content)
            if json_match:
                try:
                    parsed_content = json.loads(json_match.group())
                except:
                    parsed_content = {"raw_text": content}
            else:
                parsed_content = {"raw_text": content}
        
        return {
            "content": parsed_content,
            "token_usage": {
                "input": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
                "output": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
                "total": (response.usage_metadata.prompt_token_count + response.usage_metadata.candidates_token_count) if hasattr(response, 'usage_metadata') else 0
            },
            "model": model,
            "confidence_score": _estimate_confidence(content)
        }
        
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")


def _mock_llm_response(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """Generate mock response for development."""
    logger.warning("Using mock LLM response - set OPENAI_API_KEY or GEMINI_API_KEY for real generation")
    
    if "qa_pair" in user_prompt.lower() or "question" in user_prompt.lower():
        content = [
            {
                "question": "What is the company's revenue growth rate?",
                "answer": "Based on the financial data, the company showed a 15% year-over-year revenue growth.",
                "category": "financial_metrics"
            },
            {
                "question": "What are the main risk factors?",
                "answer": "Key risks include market volatility, regulatory changes, and competitive pressures.",
                "category": "risk_analysis"
            }
        ]
    elif "reasoning" in user_prompt.lower() or "chain" in user_prompt.lower():
        content = {
            "premise": "Analyzing company financial health",
            "steps": [
                {"step_number": 1, "reasoning": "First, examine revenue trends", "evidence": "Revenue increased 15% YoY"},
                {"step_number": 2, "reasoning": "Next, assess profitability", "evidence": "Net margin improved to 12%"},
                {"step_number": 3, "reasoning": "Finally, evaluate cash position", "evidence": "Strong cash flow generation"}
            ],
            "conclusion": "The company demonstrates solid financial health with positive growth trajectory."
        }
    elif "summary" in user_prompt.lower():
        content = {
            "title": "Financial Performance Summary",
            "key_points": ["Strong revenue growth", "Improved margins", "Solid cash position"],
            "metrics": [{"name": "Revenue", "value": 1000000, "change": 0.15}],
            "risks": ["Market volatility", "Competitive pressure"],
            "outlook": "Positive outlook for continued growth"
        }
    elif "risk" in user_prompt.lower():
        content = {
            "risks": [
                {
                    "category": "Market Risk",
                    "description": "Exposure to market fluctuations",
                    "severity": "Medium",
                    "likelihood": "High",
                    "mitigation": "Diversification strategies"
                },
                {
                    "category": "Operational Risk",
                    "description": "Supply chain disruptions",
                    "severity": "High",
                    "likelihood": "Medium",
                    "mitigation": "Multiple supplier relationships"
                }
            ]
        }
    else:
        content = {
            "metrics": [
                {"name": "Revenue", "value": 1000000, "unit": "USD", "period": "2024", "yoy_change": 0.15},
                {"name": "Net Income", "value": 120000, "unit": "USD", "period": "2024", "yoy_change": 0.10}
            ]
        }
    
    return {
        "content": content,
        "token_usage": {"input": 500, "output": 300, "total": 800},
        "model": "mock",
        "confidence_score": 0.75
    }


def _estimate_confidence(content: str) -> float:
    """Estimate confidence based on response characteristics."""
    confidence = 0.7
    
    # More specific content = higher confidence
    if len(content) > 500:
        confidence += 0.1
    
    # Contains numbers = likely more factual
    if re.search(r'\d+\.?\d*%?', content):
        confidence += 0.05
    
    # Contains hedging language = lower confidence
    hedging = ["might", "could", "possibly", "uncertain", "unclear"]
    for word in hedging:
        if word in content.lower():
            confidence -= 0.05
    
    return max(0.3, min(1.0, confidence))


def render_template(template: Dict[str, Any], document: Dict[str, Any]) -> str:
    """Render a prompt template with document data."""
    user_prompt = template.get("user_prompt_template", "")
    
    # Extract content for template
    raw_content = document.get("raw_content", {})
    
    # Prepare content summary (avoid huge prompts)
    if isinstance(raw_content, dict):
        content_str = json.dumps(raw_content, indent=2)[:8000]  # Limit size
    else:
        content_str = str(raw_content)[:8000]
    
    # Replace placeholders
    replacements = {
        "{{source}}": document.get("source", "unknown"),
        "{{ticker}}": document.get("ticker", "N/A"),
        "{{content}}": content_str,
        "{{document_type}}": document.get("document_type", "unknown"),
        "{{document_date}}": str(document.get("document_date", ""))
    }
    
    for placeholder, value in replacements.items():
        user_prompt = user_prompt.replace(placeholder, value)
    
    return user_prompt


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/sample", response_model=GenerateResponse)
async def generate_sample(request: GenerateRequest):
    """
    Generate a training sample from a document using LLM templates.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Get document
    document = get_document_by_id(db, request.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get template
    template = get_active_template(db, request.template_type)
    if not template:
        raise HTTPException(
            status_code=404, 
            detail=f"No active template found for type: {request.template_type}"
        )
    
    # Render prompt
    system_prompt = template.get("system_prompt", "")
    user_prompt = render_template(template, document)
    
    # Call LLM
    try:
        llm_result = await call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise HTTPException(status_code=502, detail=f"Generation failed: {str(e)}")
    
    # Store sample
    sample_data = {
        "raw_document_id": request.document_id,
        "template_type": request.template_type,
        "template_version": template.get("version", "v1"),
        "generated_content": llm_result["content"],
        "model_used": llm_result.get("model", request.model),
        "model_params": {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        },
        "confidence_score": llm_result.get("confidence_score"),
        "token_usage": llm_result.get("token_usage", {}),
        "generation_time_ms": llm_result.get("generation_time_ms")
    }
    
    sample_id = insert_generated_sample(db, sample_data)
    
    return GenerateResponse(
        sample_id=sample_id,
        status="success",
        template_type=request.template_type,
        generated_content=llm_result["content"],
        confidence_score=llm_result.get("confidence_score"),
        generation_time_ms=llm_result.get("generation_time_ms"),
        message="Sample generated successfully"
    )


@router.post("/batch", response_model=BatchGenerateResponse)
async def batch_generate(request: BatchGenerateRequest, background_tasks: BackgroundTasks):
    """
    Queue batch generation for multiple documents and template types.
    """
    job_id = str(uuid4())
    total_tasks = len(request.document_ids) * len(request.template_types)
    
    # Add to background tasks
    background_tasks.add_task(
        run_batch_generation,
        job_id,
        request.document_ids,
        request.template_types,
        request.model
    )
    
    return BatchGenerateResponse(
        job_id=job_id,
        status="queued",
        total_tasks=total_tasks,
        message=f"Batch generation queued: {total_tasks} samples to generate"
    )


async def run_batch_generation(
    job_id: str,
    document_ids: List[str],
    template_types: List[str],
    model: str
):
    """Background task for batch generation."""
    logger.info(f"Starting batch generation job: {job_id}")
    
    try:
        db = get_db()
    except Exception as e:
        logger.error(f"Batch generation failed - DB error: {e}")
        return
    
    success_count = 0
    error_count = 0
    
    for doc_id in document_ids:
        for template_type in template_types:
            try:
                document = get_document_by_id(db, doc_id)
                if not document:
                    error_count += 1
                    continue
                
                template = get_active_template(db, template_type)
                if not template:
                    error_count += 1
                    continue
                
                # Generate
                system_prompt = template.get("system_prompt", "")
                user_prompt = render_template(template, document)
                
                llm_result = await call_llm(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model
                )
                
                # Store
                sample_data = {
                    "raw_document_id": doc_id,
                    "template_type": template_type,
                    "template_version": template.get("version", "v1"),
                    "generated_content": llm_result["content"],
                    "model_used": llm_result.get("model", model),
                    "model_params": {"temperature": 0.7, "max_tokens": 2000},
                    "confidence_score": llm_result.get("confidence_score"),
                    "token_usage": llm_result.get("token_usage", {}),
                    "generation_time_ms": llm_result.get("generation_time_ms")
                }
                
                insert_generated_sample(db, sample_data)
                success_count += 1
                
                # Rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Batch generation error for {doc_id}/{template_type}: {e}")
                error_count += 1
    
    logger.info(f"Batch job {job_id} completed: {success_count} success, {error_count} errors")


@router.get("/templates", response_model=TemplateResponse)
async def list_templates():
    """
    List all available prompt templates.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    templates = get_all_templates(db)
    return TemplateResponse(templates=templates)


@router.post("/self-instruct")
async def generate_self_instruct(payload: SelfInstructRequest):
    """
    Generate augmented cases from gold standard seeds.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    from app.services.self_instruct import SelfInstructAugmentor

    seed_rows = get_seed_cases(db, limit=10)
    seed_cases = []
    for row in seed_rows:
        seed_cases.append(
            {
                "company": row.get("validated_facts", {}).get("company"),
                "industry": row.get("validated_facts", {}).get("industry"),
                "facts": row.get("validated_facts"),
                "cot": row.get("validated_decision", {}).get("rationale"),
                "decision": row.get("validated_decision"),
            }
        )

    augmentor = SelfInstructAugmentor()
    generated = await augmentor.generate(seed_cases, target_count=payload.target_count)

    inserted = 0
    for case in generated:
        sample_payload = {
            "raw_document_id": None,
            "template_type": "self_instruct",
            "generated_content": case,
            "model_used": os.getenv("SELF_INSTRUCT_MODEL", "gpt-4"),
            "review_status": "pending",
        }
        db.client.table("generated_samples").insert(sample_payload).execute()
        inserted += 1

    return {"status": "success", "inserted": inserted}


@router.post("/eval/run")
async def run_eval(payload: EvalRunRequest):
    """
    Run a lightweight alignment eval against gold_standard_cases.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    from app.services.eval_suite import EvalSuite

    rows = (
        db.client.table("gold_standard_cases")
        .select("*")
        .order("validation_score", desc=True)
        .limit(payload.limit)
        .execute()
    ).data or []

    predictions = [row.get("validated_decision", {}) for row in rows]
    ground_truth = [row.get("validated_decision", {}) for row in rows]

    suite = EvalSuite()
    result = suite.score(predictions, ground_truth)

    db.client.table("eval_runs").insert({
        "metric_set": "alignment-lite",
        "result": result,
        "sample_count": result.get("samples"),
    }).execute()

    return {"status": "success", "result": result}


@router.get("/templates/{template_type}")
async def get_template(template_type: str):
    """
    Get the active template for a specific type.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    template = get_active_template(db, template_type)
    if not template:
        raise HTTPException(status_code=404, detail=f"No active template for: {template_type}")
    
    return template


@router.get("/samples", response_model=SampleListResponse)
async def list_samples(
    template_type: Optional[str] = Query(None, description="Filter by template type"),
    review_status: Optional[str] = Query(None, description="Filter by review status"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Max results")
):
    """
    List generated samples with filters.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    samples = get_samples(db, template_type, review_status, offset, limit)
    
    # Get total count
    query = db.client.table("generated_samples").select("id", count="exact")
    if template_type:
        query = query.eq("template_type", template_type)
    if review_status:
        query = query.eq("review_status", review_status)
    
    result = query.execute()
    total = result.count or len(samples)
    
    return SampleListResponse(
        samples=samples,
        total=total,
        offset=offset,
        limit=limit
    )


@router.get("/samples/{sample_id}")
async def get_sample(sample_id: str):
    """
    Get a specific generated sample with source document context.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    sample = get_sample_by_id(db, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    return sample


@router.get("/queue")
async def get_review_queue(
    template_type: Optional[str] = Query(None, description="Filter by template type"),
    limit: int = Query(50, ge=1, le=100, description="Max results")
):
    """
    Get the HITL review queue - pending samples sorted by priority.
    """
    try:
        db = get_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    query = db.client.table("generated_samples").select(
        "id, template_type, generated_content, model_used, confidence_score, priority_score, created_at, raw_documents(source, ticker, document_type)"
    ).eq("review_status", "pending")
    
    if template_type:
        query = query.eq("template_type", template_type)
    
    query = query.order("priority_score", desc=True).order("created_at").limit(limit)
    
    result = query.execute()
    
    return {
        "queue": result.data or [],
        "count": len(result.data or [])
    }
