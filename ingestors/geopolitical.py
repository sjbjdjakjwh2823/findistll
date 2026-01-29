import pandas as pd
import logging
import datetime

logger = logging.getLogger(__name__)

class GeopoliticalIngestor:
    def __init__(self):
        # In a real production environment, this would query GDELT BigQuery or an API.
        # For this backfill engine without an external paid API key, we use a curated dataset of major events.
        self.events_db = [
            {"date": "2001-09-11", "headline": "9/11 Terrorist Attacks", "impact": "High", "entities": ["US", "Airline", "Defense"]},
            {"date": "2003-03-20", "headline": "US Invasion of Iraq", "impact": "High", "entities": ["US", "Iraq", "Oil"]},
            {"date": "2008-09-15", "headline": "Lehman Brothers Bankruptcy", "impact": "Critical", "entities": ["US", "Banking", "Finance"]},
            {"date": "2008-12-16", "headline": "Fed Cuts Rates to Near Zero", "impact": "High", "entities": ["US", "Fed", "Economy"]},
            {"date": "2011-08-05", "headline": "US Credit Rating Downgrade", "impact": "High", "entities": ["US", "Economy"]},
            {"date": "2016-06-23", "headline": "Brexit Referendum", "impact": "High", "entities": ["UK", "EU", "Forex"]},
            {"date": "2016-11-08", "headline": "Trump Elected President", "impact": "Medium", "entities": ["US", "Politics"]},
            {"date": "2020-03-12", "headline": "Global Market Crash (COVID-19)", "impact": "Critical", "entities": ["Global", "Health", "Economy"]},
            {"date": "2020-03-23", "headline": "Fed Announces Unlimited QE", "impact": "High", "entities": ["US", "Fed"]},
            {"date": "2022-02-24", "headline": "Russia Invades Ukraine", "impact": "High", "entities": ["Russia", "Ukraine", "Energy"]},
            {"date": "2022-03-16", "headline": "Fed Starts Hiking Rates", "impact": "High", "entities": ["US", "Fed"]},
            {"date": "2023-03-10", "headline": "Silicon Valley Bank Collapse", "impact": "High", "entities": ["US", "Banking", "Tech"]},
            {"date": "2024-01-10", "headline": "SEC Approves Bitcoin ETFs", "impact": "High", "entities": ["Crypto", "Bitcoin", "SEC"]}
        ]

    def fetch_events(self, start_date="2000-01-01", end_date=None):
        """
        Returns a list of events filtered by date range.
        """
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date) if end_date else pd.Timestamp.now()
        
        results = []
        for event in self.events_db:
            evt_date = pd.to_datetime(event['date'])
            if start <= evt_date <= end:
                results.append({
                    "event_id": f"evt_{event['date'].replace('-', '')}",
                    "headline": event['headline'],
                    "source": "HistoricalArchive",
                    "period": event['date'], # Keep as string YYYY-MM-DD for consistency
                    "related_entities": event['entities'],
                    "impact_score": 1.0 if event['impact'] == "Critical" else 0.8 if event['impact'] == "High" else 0.5
                })
        return results
