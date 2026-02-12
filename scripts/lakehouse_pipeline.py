#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict


def _spark():
    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.appName("preciso-lakehouse")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .getOrCreate()
    )


def run_pipeline(payload: Dict) -> Dict:
    spark = _spark()
    delta_root = os.getenv("DELTA_ROOT_URI", "s3a://preciso-lakehouse")
    tenant_id = payload.get("tenant_id", "public")
    ts = datetime.now(timezone.utc).isoformat()

    sample = [
        {
            "tenant_id": tenant_id,
            "doc_id": payload.get("doc_id", "sample-doc"),
            "case_id": payload.get("case_id", "sample-case"),
            "source": payload.get("source", "preciso"),
            "extracted_at": ts,
            "schema_version": "1.0",
            "metric": payload.get("metric", "Revenue"),
            "value": payload.get("value", "0"),
            "currency": payload.get("currency", "USD"),
            "unit": payload.get("unit", "currency"),
            "period_norm": payload.get("period_norm", "2025Q4"),
        }
    ]

    df = spark.createDataFrame(sample)
    bronze_path = f"{delta_root}/bronze/raw_documents/tenant_id={tenant_id}"
    silver_path = f"{delta_root}/silver/fin_facts/tenant_id={tenant_id}"
    gold_path = f"{delta_root}/gold/preciso_features/tenant_id={tenant_id}"

    (
        df.write.format("delta")
        .mode("append")
        .option("mergeSchema", "true")
        .save(bronze_path)
    )
    (
        df.write.format("delta")
        .mode("append")
        .option("mergeSchema", "true")
        .save(silver_path)
    )
    (
        df.write.format("delta")
        .mode("append")
        .option("mergeSchema", "true")
        .save(gold_path)
    )
    spark.stop()
    return {
        "status": "ok",
        "tenant_id": tenant_id,
        "bronze_path": bronze_path,
        "silver_path": silver_path,
        "gold_path": gold_path,
        "records": len(sample),
    }


if __name__ == "__main__":
    payload = json.loads(os.getenv("PRECISO_LAKEHOUSE_PAYLOAD", "{}"))
    print(json.dumps(run_pipeline(payload)))
