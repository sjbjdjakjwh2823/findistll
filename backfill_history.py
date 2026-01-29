import os
import yfinance as yf
import pandas as pd
import logging
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import sys

# 엔진 로드
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from spokes.active_engines import SpokeA, SpokeB, SpokeC, SpokeD

# 환경 변수 로드
load_dotenv("project_1/.env")

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BackfillEngine")

# Supabase 연결
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Spokes 초기화
spoke_a = SpokeA()
spoke_b = SpokeB()
spoke_c = SpokeC()
spoke_d = SpokeD()

def process_batch(records):
    """데이터를 배치로 처리하여 Supabase와 Spokes에 전송"""
    if not records: return

    # 1. 원본 데이터 저장 (Market Data)
    # 배치 사이즈가 너무 크면 Supabase가 거부할 수 있으므로 1000개씩 분할
    batch_size = 1000
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        try:
            supabase.table("market_data").upsert(batch).execute()
            logger.info(f"   -> Saved {len(batch)} rows to market_data.")
        except Exception as e:
            logger.error(f"Error saving batch to DB: {e}")

    # 2. Spoke 엔진 가동 (변환 및 저장)
    # Spokes는 내부적으로 필요한 로직을 수행하고 저장함
    # 너무 많은 데이터를 한 번에 넣으면 느리므로, 샘플링하거나 중요 데이터만 Spokes에 넘김
    # 여기서는 '종가(Close)'가 있는 데이터 전체를 넘깁니다.
    
    # Spoke 처리도 배치로 진행
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        try:
            spoke_a.process_and_store(batch, supabase) # 전략
            spoke_d.process_and_store(batch, supabase) # 그래프
            # Spoke B, C는 데이터량이 많으므로 최신 데이터 위주로 하거나 필요한 경우 활성화
            spoke_c.process_and_store(batch, supabase) # RAG (Context)
        except Exception as e:
            logger.error(f"Error in Spoke processing: {e}")

def fetch_history_market():
    logger.info("=== Starting Historical Market Data Backfill (2000-Now) ===")
    
    # 1. 자산 목록 정의
    # S&P 500 Top Holdings + Major Assets
    assets = {
        'EQUITY': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'SPY'],
        'COMMODITY': ['GLD', 'SLV', 'USO', 'CL=F', 'GC=F'], # Gold, Silver, Oil
        'MACRO': ['^TNX', '^VIX'], # 10Y Treasury, Volatility
        'CRYPTO': ['BTC-USD', 'ETH-USD', 'XRP-USD']
    }
    
    start_date = "2000-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")

    for asset_class, tickers in assets.items():
        logger.info(f"Downloading {asset_class} data...")
        
        # yfinance 배치 다운로드
        try:
            # Group by Ticker ensures we get a MultiIndex or simple DF depending on count
            data = yf.download(tickers, start=start_date, end=end_date, group_by='ticker', progress=True, interval="1d")
            
            records = []
            
            # 단일 티커일 경우와 다중 티커일 경우 구조가 다름
            if len(tickers) == 1:
                # 구조 통일
                ticker = tickers[0]
                df = data
                records.extend(parse_dataframe(df, ticker, asset_class))
            else:
                for ticker in tickers:
                    try:
                        df = data[ticker]
                        records.extend(parse_dataframe(df, ticker, asset_class))
                    except KeyError:
                        logger.warning(f"No data for {ticker}")

            logger.info(f"Processing {len(records)} records for {asset_class}...")
            process_batch(records)
            
        except Exception as e:
            logger.error(f"Failed to download {asset_class}: {e}")

def parse_dataframe(df, ticker, asset_class):
    """DataFrame을 Supabase 스키마 리스트로 변환"""
    cleaned = []
    if df.empty: return []
    
    # NaN 제거
    df = df.dropna()
    
    for index, row in df.iterrows():
        try:
            cleaned.append({
                "ticker": ticker,
                "asset_class": asset_class,
                "interval": "1d",
                "timestamp": index.isoformat(),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": int(row['Volume'])
            })
        except Exception:
            continue
    return cleaned

def fetch_financials_rag():
    logger.info("=== Starting Financials to RAG Transformation ===")
    # S&P 500 주요 기업의 재무제표를 텍스트로 변환하여 Spoke C(RAG)에 저장
    
    tickers = ['AAPL', 'MSFT', 'TSLA'] # 데모용 주요 기업
    
    for ticker in tickers:
        logger.info(f"Fetching Financials for {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            
            # 1. 대차대조표 (Balance Sheet)
            balance = stock.balance_sheet
            if not balance.empty:
                # 최근 4년치 데이터
                for date in balance.columns:
                    # 데이터를 텍스트로 요약
                    text_summary = f"Financial Report for {ticker} (Date: {date.date()}):\n"
                    for item, value in balance[date].items():
                        if pd.notna(value):
                            text_summary += f"- {item}: {value:,.0f}\n"
                    
                    # 배치 구조 생성
                    record = {
                        "dataset_name": "Financials", # 구분용
                        "fetched_at": date.isoformat(),
                        "data_content": {"text": text_summary},
                        "ticker": ticker # Spoke C가 인식하도록
                    }
                    
                    # Spoke C에 직접 주입 (DB 저장 로직은 Spoke C 내부에 있음)
                    # 여기서는 'huggingface_data' 테이블 형식을 빌려 처리하거나,
                    # Spoke C를 직접 호출하여 저장
                    
                    # Spoke C는 process_and_store에서 'dataset_name'을 처리하도록 되어 있음
                    spoke_c.process_and_store([record], supabase)
                    
            logger.info(f"Processed Financials for {ticker}")
            
        except Exception as e:
            logger.error(f"Error fetching financials for {ticker}: {e}")

if __name__ == "__main__":
    logger.info("Initializing Backfill Process...")
    
    # 1. 시장 데이터 (2000 ~ 현재)
    fetch_history_market()
    
    # 2. 재무제표 데이터 (RAG 변환)
    fetch_financials_rag()
    
    logger.info("=== Backfill Complete. Real-time server continues independently. ===")
