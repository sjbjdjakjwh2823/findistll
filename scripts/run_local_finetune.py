from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.db.registry import get_db

logger = logging.getLogger("preciso.local_finetune")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _to_jsonl(records: Iterable[Dict[str, Any]], out_path: Path) -> int:
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count


def _extract_spoke_a_records(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        record = row.get("record") or row.get("payload") or row
        if not isinstance(record, dict):
            record = {"record": record}
        items.append(record)
    return items


def _parse_training_args() -> Dict[str, Any]:
    raw = (os.getenv("PRECISO_TRAINING_ARGS") or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _build_text_records(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for rec in records:
        instruction = str(rec.get("instruction") or "").strip()
        input_text = str(rec.get("input") or "").strip()
        output_text = str(rec.get("output") or "").strip()
        if not output_text:
            continue
        prompt = instruction
        if input_text:
            prompt = f"{instruction}\n\nContext:\n{input_text}"
        out.append({"prompt": prompt, "response": output_text})
    return out


def _write_prompt_dataset(rows: List[Dict[str, str]], out_path: Path) -> int:
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def _try_import(module: str):
    try:
        return __import__(module)
    except Exception:
        return None


def _set_default_model(db, record: Dict[str, Any]) -> None:
    try:
        models = db.list_model_registry(limit=200) or []
    except Exception:
        models = []
    for m in models:
        if m.get("id") == record.get("id"):
            continue
        m["is_default"] = False
        try:
            db.upsert_model_registry(m)
        except Exception:
            continue
    record["is_default"] = True
    db.upsert_model_registry(record)


def main() -> int:
    dataset_version_id = os.getenv("PRECISO_DATASET_VERSION_ID", "").strip()
    model_name = os.getenv("PRECISO_MODEL_NAME", "preciso-default").strip()
    local_model_path = os.getenv("PRECISO_LOCAL_MODEL_PATH", "").strip()
    mlflow_run_id = os.getenv("PRECISO_MLFLOW_RUN_ID", "").strip()
    training_args = _parse_training_args()

    if not dataset_version_id:
        logger.error("PRECISO_DATASET_VERSION_ID is required.")
        return 1

    db = get_db()
    samples = db.list_spoke_a_samples(dataset_version_id, limit=200000) or []
    records = _extract_spoke_a_records(samples)
    if not records:
        logger.error("No Spoke A samples found for dataset_version_id=%s", dataset_version_id)
        return 1

    artifacts_root = Path(os.getenv("PRECISO_TRAINING_DIR", "artifacts/training_runs"))
    run_id = mlflow_run_id or f"local_{dataset_version_id}_{int(datetime.now().timestamp())}"
    run_dir = artifacts_root / run_id
    _ensure_dir(run_dir)

    dataset_path = run_dir / "spoke_a_sft.jsonl"
    count = _to_jsonl(records, dataset_path)
    prompt_records = _build_text_records(records)
    prompt_path = run_dir / "spoke_a_prompt.jsonl"
    prompt_count = _write_prompt_dataset(prompt_records, prompt_path)

    logger.info("Prepared %d samples for dataset_version_id=%s", count, dataset_version_id)
    logger.info("Prepared %d prompt samples", prompt_count)
    logger.info("Dataset path: %s", dataset_path)
    logger.info("Prompt dataset path: %s", prompt_path)
    logger.info("Model name: %s", model_name)
    if local_model_path:
        logger.info("Local model path: %s", local_model_path)
        if not Path(local_model_path).exists():
            logger.warning("Local model path does not exist; training will be skipped.")
            return 0

    # Minimal local training hook.
    # Users can replace this script or wrap it to call their own fine-tuner.
    backend = (os.getenv("LOCAL_TRAINING_BACKEND") or "export_only").strip().lower()
    if backend == "export_only":
        logger.info("LOCAL_TRAINING_BACKEND=export_only. Dataset exported; no training executed.")
        return 0

    if backend == "qlora":
        transformers = _try_import("transformers")
        peft = _try_import("peft")
        bitsandbytes = _try_import("bitsandbytes")
        torch = _try_import("torch")

        if not (transformers and peft and bitsandbytes and torch):
            logger.error("QLoRA deps missing. Install: transformers, peft, bitsandbytes, accelerate, torch.")
            return 1

        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            Trainer,
            TrainingArguments,
            DataCollatorForLanguageModeling,
        )
        from peft import LoraConfig, get_peft_model
        from datasets import load_dataset

        model_id = local_model_path or model_name
        if not model_id:
            logger.error("Local model path or model name is required for QLoRA.")
            return 1

        dataset = load_dataset("json", data_files=str(prompt_path), split="train")
        if len(dataset) == 0:
            logger.error("No prompt records to train.")
            return 1

        tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        def _format(example: Dict[str, Any]) -> Dict[str, Any]:
            text = f"{example['prompt']}\n\nAnswer:\n{example['response']}"
            return {"text": text}

        dataset = dataset.map(_format)
        tokenized = dataset.map(
            lambda ex: tokenizer(ex["text"], truncation=True, max_length=int(training_args.get("max_length", 1024))),
            remove_columns=dataset.column_names,
        )

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=getattr(torch, training_args.get("compute_dtype", "float16")),
        )

        model = AutoModelForCausalLM.from_pretrained(model_id, quantization_config=bnb_config, device_map="auto")
        lora_cfg = LoraConfig(
            r=int(training_args.get("lora_r", 8)),
            lora_alpha=int(training_args.get("lora_alpha", 16)),
            lora_dropout=float(training_args.get("lora_dropout", 0.05)),
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_cfg)

        output_dir = str(run_dir / "qlora_out")
        args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=float(training_args.get("epochs", 1)),
            per_device_train_batch_size=int(training_args.get("batch_size", 1)),
            gradient_accumulation_steps=int(training_args.get("grad_accum", 8)),
            learning_rate=float(training_args.get("learning_rate", 2e-4)),
            fp16=True,
            logging_steps=int(training_args.get("logging_steps", 10)),
            save_steps=int(training_args.get("save_steps", 200)),
            save_total_limit=int(training_args.get("save_total_limit", 2)),
        )
        trainer = Trainer(
            model=model,
            args=args,
            train_dataset=tokenized,
            data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
        )
        trainer.train()
        trainer.save_model(output_dir)
        logger.info("QLoRA training completed. Output: %s", output_dir)

        # Register as default serving model.
        model_record = {
            "id": f"local_{run_id}",
            "name": f"{model_name}-finetuned-{run_id[:8]}",
            "provider": "local",
            "base_url": os.getenv("LOCAL_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or os.getenv("OLLAMA_BASE_URL", "").rstrip("/") + "/v1",
            "model": str(output_dir),
            "purpose": "llm",
            "metadata": {
                "dataset_version_id": dataset_version_id,
                "mlflow_run_id": mlflow_run_id,
                "trained_at": _utc_now(),
                "backend": "qlora",
            },
        }
        _set_default_model(db, model_record)
        return 0

    logger.warning("LOCAL_TRAINING_BACKEND=%s not implemented; falling back to export_only.", backend)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
