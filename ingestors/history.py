import ccxt
import yfinance as yf
import pandas as pd
import logging
import datetime
import time

logger = logging.getLogger(__name__)

class HistoricalIngestor:
    def __init__(self):
        self.sp500_tickers = self._get_sp500_tickers()
        self.crypto_map = {
            'BTC': 'BTC-USD',
            'ETH': 'ETH-USD',
            'SOL': 'SOL-USD',
            'XRP': 'XRP-USD'
        }
        
    def _get_sp500_tickers(self):
        # Fallback list if scraping fails, usually we'd scrape Wikipedia
        # For demo, returning top 10 to avoid API bans during dev
        return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'BRK-B', 'JPM', 'V']

    def fetch_full_history(self, start_date="2000-01-01", end_date=None):
        """
        Fetches historical data for Crypto, Macro, and S&P 500.
        Returns a massive list of records.
        """
        all_data = []
        if not end_date:
            end_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 1. Macro & Commodities (Gold, Oil, 10Y Yield, Silver, Copper, 2Y Yield)
        # ^GSPC: S&P 500 Index
        macro_tickers = ['^TNX', 'GC=F', 'CL=F', '^GSPC', 'SI=F', 'HG=F', '^IRX']
        logger.info(f"Fetching Macro History ({start_date} ~ {end_date})...")
        macro_data = self._fetch_yfinance(macro_tickers, start_date, end_date, "Macro")
        all_data.extend(macro_data)
        
        # 2. Crypto (Availability depends on launch date)
        logger.info(f"Fetching Crypto History ({start_date} ~ {end_date})...")
        # Use yfinance for long history of crypto
        crypto_tickers = list(self.crypto_map.values())
        crypto_data = self._fetch_yfinance(crypto_tickers, start_date, end_date, "Crypto")
        all_data.extend(crypto_data)
        
        # 3. S&P 500 Fundamentals (Quarterly) & Price
        logger.info(f"Fetching S&P 500 History ({len(self.sp500_tickers)} companies)...")
        stock_data = self._fetch_yfinance(self.sp500_tickers, start_date, end_date, "Equity")
        all_data.extend(stock_data)
        
        return all_data

    def _fetch_yfinance(self, tickers, start, end, asset_class):
        data = []
        try:
            # Download in bulk
            # group_by='ticker' makes it easier to process
            df = yf.download(tickers, start=start, end=end, group_by='ticker', progress=False, threads=True)
            
            # If single ticker, df columns are just Open, Close...
            # If multiple, columns are MultiIndex (Ticker, PriceType) or (PriceType, Ticker)
            
            if len(tickers) == 1:
                ticker = tickers[0]
                # Reformat single ticker DF to match multi-ticker loop structure
                df.columns = pd.MultiIndex.from_product([[ticker], df.columns])
            
            # Iterate through each ticker in the columns
            # Level 0 is Ticker (if group_by='ticker')
            
            downloaded_tickers = df.columns.get_level_values(0).unique()
            
            for ticker in downloaded_tickers:
                # Extract dataframe for this ticker
                ticker_df = df[ticker].copy()
                ticker_df = ticker_df.dropna(how='all') # Remove days with no data
                
                # Reset index to get Date column
                ticker_df = ticker_df.reset_index()
                
                # Convert to record list
                for _, row in ticker_df.iterrows():
                    dt = row['Date'].isoformat()
                    
                    # We store OHLCV + Asset Class
                    # To save space, we might just store Close for old history, 
                    # but prompt asked for "Financials" too.
                    
                    # Basic Price Data
                    base_record = {
                        "entity": ticker,
                        "period": dt,
                        "unit": "USD",
                        "source_tier": "tier2_hist",
                        "meta": {"asset_class": asset_class}
                    }
                    
                    if pd.notna(row.get('Close')):
                        data.append({**base_record, "concept": "MarketClose", "value": float(row['Close'])})
                    if pd.notna(row.get('Volume')):
                        data.append({**base_record, "concept": "MarketVolume", "value": float(row['Volume']), "unit": "Shares"})
                        
        except Exception as e:
            logger.error(f"History Fetch Error for {tickers}: {e}")
            
        return data

    def fetch_fundamentals(self):
        """
        Fetches annual/quarterly financials for S&P 500.
        Note: yfinance only provides last 4 years of financials.
        For 2000-2023, we would need a paid API (Polygon/AlphaVantage).
        We will scrape what is available.
        """
        data = []
        for ticker in self.sp500_tickers:
            try:
                stock = yf.Ticker(ticker)
                
                # Quarterly Financials
                q_fin = stock.quarterly_financials
                if not q_fin.empty:
                    for date, row in q_fin.T.iterrows():
                        for concept, value in row.items():
                            if pd.notna(value):
                                data.append({
                                    "entity": ticker,
                                    "period": date.isoformat(),
                                    "concept": str(concept).replace(" ", ""),
                                    "value": float(value),
                                    "unit": "USD",
                                    "source_tier": "fundamental"
                                })
            except Exception as e:
                continue
        return data
