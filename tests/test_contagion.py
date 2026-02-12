from app.services.contagion import contagion_model
import json

def test_modeling_backtest():
    print("🚀 Running 2023 Bank Crisis Contagion Velocity Backtest...")
    
    result = contagion_model.run_backtest_2023()
    
    print("\n✅ Backtest Results:")
    print(f"  - Model: {result['model_version']}")
    print(f"  - Primary Velocities: {json.dumps(result['primary_velocity'], indent=2)}")
    print(f"  - Risk Transfer Coeff: {result['risk_transfer_coefficient']}")
    print(f"  - Summary: {result['summary']}")
    
    print("\n🔮 Predictions for current Market Sentiment:")
    predictions = contagion_model.predict_next_nodes("General Market", 0.3)
    for p in predictions:
        print(f"  - {p['node']}: Prob {p['probability']*100}% | Est. Time: {p['estimated_time_days']} days")

if __name__ == "__main__":
    run_modeling_backtest()
