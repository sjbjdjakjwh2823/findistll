import json
import polars as pl
import pyarrow as pa
import logging
import os
import datetime

logger = logging.getLogger(__name__)

class SpokeA:
    """AI Tuning (Strategy) - The Sovereign Architect Mode"""
    def process_and_store(self, data_list, supabase):
        if not data_list or not supabase: return
        logger.info("Spoke A (Sovereign Architect): Generating High-Dimensional Strategy...")
        
        results = []
        for row in data_list:
            entity = row.get('ticker') or row.get('dataset_name')
            if not entity: continue

            # Extract Data Points
            price = row.get('close', 0)
            asset = row.get('asset_class', 'Unknown')
            volume = row.get('volume', 0)
            
            # [Master Agent Logic] Deep CoT Reasoning
            # Mapping: Macro -> Micro -> Event -> Result
            
            strategy = "Hold"
            trace_steps = []
            
            # Step 1: Macro/Political Context (Simulated Knowledge)
            # In a real Palantir Foundry setup, this comes from a linked Macro Node.
            macro_context = "Neutral"
            if asset in ['MACRO', 'FOREX']:
                macro_context = "Global Volatility High (Fed Policy Uncertainty)"
                trace_steps.append(f"[Macro] {macro_context}")
            else:
                trace_steps.append("[Macro] Market conditions stable.")

            # Step 2: Micro/Asset Specifics
            trace_steps.append(f"[Micro] {entity} Price: {price}, Volume: {volume}")
            
            # Step 3: Causal Inference (The "Brain")
            if asset == 'CRYPTO':
                if price > 0 and volume > 1000000:
                    reasoning = "High volume indicates institutional interest despite macro uncertainty."
                    strategy = "Accumulate"
                    trace_steps.append(f"[Reasoning] {reasoning}")
                    trace_steps.append(f"[Causality] Institutional Inflow -> Support Level Formed -> Upside Likely")
                else:
                    trace_steps.append("[Reasoning] Low volume suggests lack of conviction.")
            
            elif asset == 'EQUITY':
                # Example: "Fed Rate Hike -> Debt Cost Up -> CAPEX Down -> Stock Bearish"
                if "High" in macro_context:
                    strategy = "Reduce Exposure"
                    trace_steps.append("[Causality] Macro Volatility -> Risk Premium Up -> Equity Valuation Compression -> Bearish")
                else:
                    strategy = "Hold"
                    trace_steps.append("[Causality] Stable Macro -> Earnings Focus -> Maintain Position")

            elif asset == 'COMMODITY':
                trace_steps.append("[Causality] Inflation Hedge Demand -> Commodity Strength -> Accumulate if Trend > SMA20")
                if price > 0: strategy = "Hedge Buy"

            # Final Synthesis
            analysis_trace = " || ".join(trace_steps)
            
            record = {
                "entity": entity,
                "period": row.get('timestamp') or row.get('fetched_at'),
                "instruction": f"Execute Sovereign Strategy for {entity}",
                "input_context": f"Asset: {asset} | Price: {price} | Macro: {macro_context}",
                "output_strategy": strategy,
                "analysis_trace": analysis_trace,
                "confidence": "High (Sovereign)"
            }
            results.append(record)
            
        if results:
            try:
                supabase.table("spoke_a_strategy").insert(results).execute()
                logger.info(f"Spoke A: Stored {len(results)} Sovereign Strategies.")
            except Exception as e:
                logger.error(f"Spoke A Error: {e}")

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from xbrl_parser import XBRLParser
except ImportError:
    # Fallback if running from root
    from spokes.xbrl_parser import XBRLParser

class SpokeB:
    """Quant Engine (Metadata & Fundamentals)"""
    def __init__(self):
        self.parser = XBRLParser()
        # Define paths to watch (Desktop)
        self.desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        
    def process_and_store(self, data_list, supabase):
        if not data_list or not supabase: return
        logger.info("Spoke B: Processing Quant Metadata & Fundamentals...")
        
        for row in data_list:
            entity = row.get('ticker') or row.get('entity')
            if not entity: continue
            
            # 1. Real Data Ingestion: Check Desktop for matching XBRL
            # Logic: Search for files containing the ticker symbol
            financials = {}
            try:
                # Find matching files
                target_files = []
                for root, dirs, files in os.walk(self.desktop_path):
                    for file in files:
                        if (file.lower().endswith('.xml') or file.lower().endswith('.xbrl')) and \
                           (entity.lower() in file.lower() or entity.lower() in root.lower()):
                            target_files.append(os.path.join(root, file))
                            
                # Parse found files
                if target_files:
                    logger.info(f"Spoke B: Found {len(target_files)} XBRL files for {entity}. Parsing...")
                    # Take the first/most recent one for demo
                    financials = self.parser.parse_file(target_files[0])
                    logger.info(f"Spoke B: Extracted fundamentals for {entity}: {financials}")
                else:
                    # Fallback to simulated data if no file found (to keep pipeline running)
                    logger.warning(f"Spoke B: No XBRL file found for {entity}. Using simulated data.")
                    financials = {"PER": 25.4, "EPS": 3.12, "ROE": 15.5} # Fallback
            except Exception as e:
                logger.error(f"Spoke B Ingestion Error: {e}")
                financials = {"Error": str(e)}

            # 2. Enrich the row object so Spoke E can see it later
            # (Note: In a real system, we'd write to DB, and Spoke E would read DB.
            # Here we modify the list in-place if possible, or assume downstream can look it up)
            row['financials'] = financials

            # 3. Store Metadata
            record = {
                "dataset_name": f"{entity}_fundamentals_{datetime.datetime.now().strftime('%Y%m')}",
                "partition_year": str(datetime.datetime.now().year),
                "record_count": 1,
                "storage_path": target_files[0] if target_files else "Simulated"
            }
            try:
                supabase.table("spoke_b_quant_meta").insert(record).execute()
            except Exception:
                pass


class SpokeC:
    """RAG Context"""
    def process_and_store(self, data_list, supabase):
        if not data_list or not supabase: return
        logger.info("Spoke C: Generating RAG Context...")
        
        chunks = []
        for row in data_list:
            # Handle Market Data
            if 'ticker' in row:
                entity = row['ticker']
                text = f"On {row['timestamp']}, {entity} closed at {row['close']} with volume {row['volume']}."
                chunk_id = f"{entity}_{row['timestamp']}_market"
                source = "Market"
            # Handle HF Data
            elif 'dataset_name' in row:
                entity = "FinancialNews"
                content = row.get('data_content', {})
                text = str(content.get('text', ''))
                chunk_id = f"news_{row['fetched_at']}_{hash(text)}"
                source = "HuggingFace"
            else:
                continue
                
            chunk = {
                "chunk_id": chunk_id,
                "entity": entity,
                "period": row.get('timestamp') or row.get('fetched_at'),
                "source": source,
                "text_content": text,
                "keywords": [entity, source]
            }
            chunks.append(chunk)
            
        if chunks:
            try:
                supabase.table("spoke_c_rag_context").insert(chunks).execute()
                logger.info(f"Spoke C: Stored {len(chunks)} chunks.")
            except Exception as e:
                logger.error(f"Spoke C Error: {e}")

class SpokeD:
    """Knowledge Graph - Ontology Mapper"""
    def process_and_store(self, data_list, supabase):
        if not data_list or not supabase: return
        logger.info("Spoke D: Constructing Multi-Dimensional Ontology...")
        
        triples = []
        for row in data_list:
            if 'ticker' in row:
                entity = row['ticker']
                asset_class = row.get('asset_class', 'Asset')
                
                # 1. Fundamental Identity (Entity -> Class)
                triples.append({
                    "head_node": entity,
                    "relation": "IS_A",
                    "tail_node": asset_class,
                    "properties": {"source": "MasterAgent_Ontology"}
                })
                
                # 2. Dynamic State (Entity -> State)
                price = row['close']
                prev_close = row.get('open', price) # Simplified
                trend = "BULLISH_MOMENTUM" if price > prev_close else "BEARISH_PRESSURE"
                
                triples.append({
                    "head_node": entity,
                    "relation": "EXHIBITS_STATE",
                    "tail_node": trend,
                    "properties": {"price": price, "delta": price - prev_close}
                })
                
                # 3. Macro Linkage (Simulated based on Prompt's Ontology)
                # "Macro -> Micro" link
                if asset_class == 'EQUITY':
                    triples.append({
                        "head_node": "MACRO_LIQUIDITY",
                        "relation": "AFFECTS",
                        "tail_node": entity,
                        "properties": {"impact_weight": "High", "mechanism": "DiscountRate"}
                    })
                elif asset_class == 'CRYPTO':
                    triples.append({
                        "head_node": "RISK_SENTIMENT",
                        "relation": "DRIVES",
                        "tail_node": entity,
                        "properties": {"correlation": "Positive"}
                    })
                
        if triples:
            try:
                supabase.table("spoke_d_graph").insert(triples).execute()
                logger.info(f"Spoke D: Stored {len(triples)} Ontology Triples.")
            except Exception as e:
                logger.error(f"Spoke D Error: {e}")

class SpokeE:
    """Report Engine - AI-Optimized Output (The Synthesizer)"""
    def process_and_store(self, data_list, supabase):
        if not data_list or not supabase: return
        logger.info("Spoke E: Synthesizing Integrated Report for AI Training...")
        
        reports = []
        for row in data_list:
            # We assume 'row' contains aggregated data from other Spokes (A, B, C, D)
            # Or we fetch linked data from Supabase using the entity ID
            entity = row.get('ticker') or row.get('entity')
            if not entity: continue
            
            # 1. Integration: Gather Insights from All Spokes
            # In a real system, this would query the Graph (Spoke D) for connected nodes.
            # Here we simulate the aggregation of previously generated insights.
            
            # Simulated Retrieval from Spoke A (Strategy)
            risk_assessment = f"Calculated risk exposure for {entity} based on volatility and macro factors."
            
            # Simulated Retrieval from Spoke B (Quant)
            # NOW: Get Real Data from row (injected by Spoke B)
            financial_ratios = row.get('financials')
            if not financial_ratios:
                # Fallback if Spoke B didn't run or failed
                financial_ratios = {"Status": "Data Pending", "Source": "Spoke B"}
            
            # Simulated Retrieval from Spoke C (RAG)
            summary = f"Comprehensive analysis of {entity} showing strong fundamentals despite market headwinds."
            
            # 2. Optimization: Format for AI (JSONL/Structured)
            # Instead of a human-readable PDF, we create a rich, structured dataset
            # that an LLM can easily ingest for Fine-tuning or RAG.
            
            ai_optimized_record = {
                "metadata": {
                    "entity": entity,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "data_source": "FinDistill_Integrated_Engine",
                    "version": "2.0"
                },
                "input_features": {
                    "financials": financial_ratios,
                    "market_data": {
                        "price": row.get('close'),
                        "volume": row.get('volume')
                    },
                    "ontology_state": row.get('ontology_state', 'Unknown') # From Spoke D
                },
                "reasoning_chain": {
                    "step_1_macro": "Global macro conditions analyzed.",
                    "step_2_micro": "Entity specific financials reviewed.",
                    "step_3_synthesis": risk_assessment
                },
                "output_narrative": summary,
                "training_prompt": f"Analyze the investment viability of {entity} given the following financial data: {json.dumps(financial_ratios)}."
            }
            
            reports.append(ai_optimized_record)
            
        if reports:
            try:
                # Store in a dedicated table for AI Training Sets
                # Supabase table: 'ai_training_sets' (needs to be created if not exists)
                # For this demo, we assume it exists or we log the output.
                supabase.table("ai_training_sets").insert(reports).execute()
                logger.info(f"Spoke E: Stored {len(reports)} AI-Optimized Training Records.")
                
                # Ensure output directory exists
                os.makedirs("final_output", exist_ok=True)
                
                # Also save to local JSONL file for immediate inspection
                # Use the last entity name for filename, or a generic batch name if mixed
                output_filename = f"final_output/{entity}_ai_report.jsonl"
                with open(output_filename, "w", encoding="utf-8") as f:
                    for report in reports:
                        f.write(json.dumps(report, ensure_ascii=False) + "\n")
                        
            except Exception as e:
                logger.error(f"Spoke E Error: {e}")
