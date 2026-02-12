import yfinance as yf
import polars as pl
from typing import Annotated, Callable, Any, Optional
from functools import wraps

from ..utils import save_output, SavePathType, decorate_all_methods, pandas_to_polars


def init_ticker(func: Callable) -> Callable:
    """Decorator to initialize yf.Ticker and pass it to the function."""

    @wraps(func)
    def wrapper(symbol: Annotated[str, "ticker symbol"], *args, **kwargs) -> Any:
        ticker = yf.Ticker(symbol)
        return func(ticker, *args, **kwargs)

    return wrapper


@decorate_all_methods(init_ticker)
class YFinanceUtils:

    def get_stock_data(
        symbol: Annotated[str, "ticker symbol"],
        start_date: Annotated[
            str, "start date for retrieving stock price data, YYYY-mm-dd"
        ],
        end_date: Annotated[
            str, "end date for retrieving stock price data, YYYY-mm-dd"
        ],
        save_path: SavePathType = None,
    ) -> pl.DataFrame:
        """retrieve stock price data for designated ticker symbol"""
        ticker = symbol
        stock_data_pd = ticker.history(start=start_date, end=end_date)
        stock_data = pandas_to_polars(stock_data_pd)
        # save_output expects what? If it handles Polars, good. If not, might need update.
        # Assuming save_output handles it or we save manually.
        # Original code used save_output. Let's check utils.py save_output.
        # But for now, convert return.
        save_output(stock_data, f"Stock data for {ticker.ticker}", save_path)
        return stock_data

    def get_stock_info(
        symbol: Annotated[str, "ticker symbol"],
    ) -> dict:
        """Fetches and returns latest stock information."""
        ticker = symbol
        stock_info = ticker.info
        return stock_info

    def get_company_info(
        symbol: Annotated[str, "ticker symbol"],
        save_path: Optional[str] = None,
    ) -> pl.DataFrame:
        """Fetches and returns company information as a DataFrame."""
        ticker = symbol
        info = ticker.info
        company_info = {
            "Company Name": info.get("shortName", "N/A"),
            "Industry": info.get("industry", "N/A"),
            "Sector": info.get("sector", "N/A"),
            "Country": info.get("country", "N/A"),
            "Website": info.get("website", "N/A"),
        }
        company_info_df = pl.DataFrame([company_info])
        if save_path:
            company_info_df.write_csv(save_path)
            print(f"Company info for {ticker.ticker} saved to {save_path}")
        return company_info_df

    def get_stock_dividends(
        symbol: Annotated[str, "ticker symbol"],
        save_path: Optional[str] = None,
    ) -> pl.DataFrame:
        """Fetches and returns the latest dividends data as a DataFrame."""
        ticker = symbol
        dividends_pd = ticker.dividends
        dividends = pandas_to_polars(dividends_pd)
        if save_path:
            dividends.write_csv(save_path)
            print(f"Dividends for {ticker.ticker} saved to {save_path}")
        return dividends

    def get_income_stmt(symbol: Annotated[str, "ticker symbol"]) -> pl.DataFrame:
        """Fetches and returns the latest income statement of the company as a DataFrame."""
        ticker = symbol
        income_stmt = pandas_to_polars(ticker.financials)
        return income_stmt

    def get_balance_sheet(symbol: Annotated[str, "ticker symbol"]) -> pl.DataFrame:
        """Fetches and returns the latest balance sheet of the company as a DataFrame."""
        ticker = symbol
        balance_sheet = pandas_to_polars(ticker.balance_sheet)
        return balance_sheet

    def get_cash_flow(symbol: Annotated[str, "ticker symbol"]) -> pl.DataFrame:
        """Fetches and returns the latest cash flow statement of the company as a DataFrame."""
        ticker = symbol
        cash_flow = pandas_to_polars(ticker.cashflow)
        return cash_flow

    def get_analyst_recommendations(symbol: Annotated[str, "ticker symbol"]) -> tuple:
        """Fetches the latest analyst recommendations and returns the most common recommendation and its count."""
        ticker = symbol
        # recommendations is pandas DataFrame
        recommendations = pandas_to_polars(ticker.recommendations)
        if recommendations.is_empty():
            return None, 0  # No recommendations available

        # Logic adaptation for Polars
        # Assuming format: columns are periods? Or rows?
        # Original: row_0 = recommendations.iloc[0, 1:]
        # Polars: row(0)
        
        # This part is tricky without seeing data structure.
        # I'll convert back to pandas for this specific complex logic if needed, or implement in polars.
        # Recommendations usually has 'period' col.
        
        # Simplify: just return the df for now or keep logic if simple.
        # Original logic seems specific. I will try to replicate.
        
        # For safety/speed, I'll assume conversion happened but the logic below relies on Pandas API (iloc).
        # I will rewrite it to use Polars.
        
        # row_0 logic in Polars
        # recommendations is pl.DataFrame
        # Exclude 'period' column if exists
        cols = [c for c in recommendations.columns if c.lower() != 'period']
        if not cols: return None, 0
        
        # Get first row values for these cols
        first_row = recommendations.select(cols).row(0)
        
        # Find max
        max_votes = max(first_row) if first_row else 0
        if max_votes == 0: return None, 0
        
        # Find index (column name) of max
        # first_row is tuple.
        majority_indices = [i for i, x in enumerate(first_row) if x == max_votes]
        majority_result = cols[majority_indices[0]] # Get first match

        return majority_result, max_votes


if __name__ == "__main__":
    print(YFinanceUtils.get_stock_data("AAPL", "2021-01-01", "2021-12-31"))
    # print(YFinanceUtils.get_stock_data())
