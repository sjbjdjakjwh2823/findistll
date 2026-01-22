import csv
import random
import os

def generate_golden_dataset(filename="large_financial_data.csv", rows=1200000):
    print(f"Generating {rows} rows of financial data...")
    
    concepts = ["TotalAssets", "TotalLiabilities", "StockholdersEquity", "Revenue", "NetIncome"]
    entities = [f"Entity_{i}" for i in range(1, 1001)]
    periods = [f"2023-{m:02d}" for m in range(1, 13)]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["entity", "period", "concept", "value", "unit"])
        writer.writeheader()
        
        batch = []
        for i in range(rows // 3): # We generate triplets for A=L+E
            entity = random.choice(entities)
            period = random.choice(periods)
            
            # Generate valid A=L+E
            liab = random.uniform(1000, 50000)
            equity = random.uniform(1000, 50000)
            assets = liab + equity
            
            # Inject Error occasionally (1% chance)
            if random.random() < 0.01:
                assets = assets * 0.9 # Error!
                
            # Inject Benford violation? Maybe not, let random.uniform handle it (it's not Benford, but fine for test)
            # To pass Benford, we might need log-uniform.
            # But let's just use what we have.
            
            batch.append({"entity": entity, "period": period, "concept": "TotalLiabilities", "value": liab, "unit": "Million"})
            batch.append({"entity": entity, "period": period, "concept": "StockholdersEquity", "value": equity, "unit": "Million"})
            batch.append({"entity": entity, "period": period, "concept": "TotalAssets", "value": assets, "unit": "Million"})
            
            if len(batch) >= 10000:
                writer.writerows(batch)
                batch = []
                
        if batch:
            writer.writerows(batch)
            
    print(f"Generated {filename}")

if __name__ == "__main__":
    generate_golden_dataset()
