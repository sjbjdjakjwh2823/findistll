import ccxt
import yfinance as yf
import pandas as pd
import logging
import datetime
import time

logger = logging.getLogger(__name__)

class CryptoIngestor:
    def __init__(self):
        self.exchanges = {
            'binance': ccxt.binance(),
            'upbit': ccxt.upbit()
        }
        self.symbols_map = {
            'BTC': 'BTC/USDT',
            'ETH': 'ETH/USDT',
            'XRP': 'XRP/USDT',
            'SOL': 'SOL/USDT',
            'USDT': 'BTC/USDT', 
            'USDC': 'USDC/USDT' 
        }

    def fetch_ohlcv(self, symbol_key='BTC', timeframe='1m', limit=100):
        symbol = self.symbols_map.get(symbol_key, symbol_key)
        exchange = self.exchanges['binance']
        
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            data = []
            for row in ohlcv:
                ts = row[0]
                dt = datetime.datetime.fromtimestamp(ts/1000).isoformat()
                
                # Wide format for Hub compatibility
                entry = {
                    "entity": symbol_key,
                    "period": dt,
                    "date": dt, # Hub uses date sometimes
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "unit": "USDT",
                    "source_tier": "tier1" # Crypto API is high confidence
                }
                data.append(entry)
                    
            return data
        except Exception as e:
            logger.error(f"Error fetching crypto data for {symbol}: {e}")
            return []

    def check_stablecoin_peg(self, symbol='USDC/USDT'):
        try:
            ticker = self.exchanges['binance'].fetch_ticker(symbol)
            last_price = ticker['last']
            
            status = "Stable"
            if abs(last_price - 1.0) > 0.01: 
                status = "De-pegging Detected"
                
            # Return as a special event row or meta
            # For Hub, we treat this as a metadata injection side-channel usually,
            # but let's return a record that can be merged.
            return {
                "entity": symbol.split('/')[0],
                "period": datetime.datetime.now().isoformat(),
                "peg_status": status,
                "peg_price": last_price
            }
        except Exception as e:
            logger.error(f"Error checking peg for {symbol}: {e}")
            return None

class MacroIngestor:
    def fetch_data(self, tickers=['^TNX', 'GC=F'], period='1d', interval='1m'):
        data = []
        try:
            df = yf.download(tickers, period=period, interval=interval, progress=False)
            if df.empty: return []

            df = df.reset_index()
            # Flatten multi-index columns if present
            # yfinance v0.2+ returns (Price, Ticker) as columns
            
            # Simple handling: Iterate rows and extract
            is_multi = isinstance(df.columns, pd.MultiIndex)
            
            for index, row in df.iterrows():
                dt = row.iloc[0].isoformat()
                
                # List of tickers to process
                target_tickers = tickers if isinstance(tickers, list) else [tickers]
                
                for ticker in target_tickers:
                    entity_name = self._map_name(ticker)
                    
                    if is_multi:
                        # Access via (PriceType, Ticker)
                        try:
                            # We construct a wide record per entity
                            c = row['Close'][ticker]
                            o = row['Open'][ticker] if 'Open' in df.columns else c
                            h = row['High'][ticker] if 'High' in df.columns else c
                            l = row['Low'][ticker] if 'Low' in df.columns else c
                            v = row['Volume'][ticker] if 'Volume' in df.columns else 0
                        except KeyError:
                            continue
                    else:
                        c = row['Close']
                        o = row['Open']
                        h = row['High']
                        l = row['Low']
                        v = row['Volume']
                        
                    if pd.notna(c):
                        data.append({
                            "entity": entity_name,
                            "period": dt,
                            "date": dt,
                            "open": float(o),
                            "high": float(h),
                            "low": float(l),
                            "close": float(c),
                            "volume": float(v),
                            "unit": "Points",
                            "source_tier": "tier2"
                        })
                        
            return data
        except Exception as e:
            logger.error(f"Error fetching macro data: {e}")
            return []

    def _map_name(self, ticker):
        map_dict = {
            '^TNX': 'US10Y_Treasury',
            'GC=F': 'Gold',
            'CL=F': 'CrudeOil'
        }
        return map_dict.get(ticker, ticker)

class NewsIngestor:
    def fetch_news(self):
        # Returns a dict of entity -> latest_news_meta
        return {
            "BTC": {"headline": "Bitcoin surges as inflation fears ease", "source": "Simulated"},
            "US10Y_Treasury": {"headline": "Fed signals rate hike pause", "source": "Simulated"}
        }
