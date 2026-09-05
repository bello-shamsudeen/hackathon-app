import joblib
import pandas as pd
import numpy as np

# Load APP data and compute scaling factors
df_app = pd.read_csv('data/app_channel_data.csv')
app_features = ['typing_speed_deviation', 'pasted_char_ratio', 'screen_sequence_anomaly', 'amount_deviation']
APP_FEATURE_SCALES = df_app[app_features].std().to_dict()

# Load USSD data and compute scaling factors
df_ussd = pd.read_csv('data/ussd_channel_data.csv')
ussd_features = ['amount_deviation', 'time_of_day_deviation', 'session_retry_deviation', 'sim_swap_risk']
USSD_FEATURE_SCALES = df_ussd[ussd_features].std().to_dict()

def score_app_session(feature_dict: dict) -> dict:
    model = joblib.load('models/app_model.pkl')
    X = pd.DataFrame([feature_dict], columns=app_features)
    prob = model.predict_proba(X)[0][1]
    risk_score = round(float(prob * 100), 2)
    importances = model.feature_importances_
    
    weighted_scores = []
    for i, feature_name in enumerate(app_features):
        deviation = abs(feature_dict[feature_name])
        scale = APP_FEATURE_SCALES[feature_name]
        norm_score = importances[i] * (deviation / scale) if scale > 0 else 0
        weighted_scores.append(norm_score)
        
    top_indices = np.argsort(weighted_scores)[-2:][::-1]
    top_features = [[app_features[i], feature_dict[app_features[i]]] for i in top_indices]
    
    return {
        "user_id": feature_dict["user_id"],
        "channel": "app",
        "risk_score": risk_score,
        "top_features": top_features,
        "session_count": 10
    }

def score_ussd_session(feature_dict: dict) -> dict:
    model = joblib.load('models/ussd_model.pkl')
    X = pd.DataFrame([feature_dict], columns=ussd_features)
    prob = model.predict_proba(X)[0][1]
    risk_score = round(float(prob * 100), 2)
    importances = model.feature_importances_
    
    weighted_scores = []
    for i, feature_name in enumerate(ussd_features):
        deviation = abs(feature_dict[feature_name])
        scale = USSD_FEATURE_SCALES[feature_name]
        norm_score = importances[i] * (deviation / scale) if scale > 0 else 0
        weighted_scores.append(norm_score)
        
    top_indices = np.argsort(weighted_scores)[-2:][::-1]
    top_features = [[ussd_features[i], feature_dict[ussd_features[i]]] for i in top_indices]
    
    return {
        "user_id": feature_dict.get("user_id", "unknown"),
        "channel": "ussd",
        "risk_score": risk_score,
        "top_features": top_features,
        "session_count": 10
    }

if __name__ == "__main__":
    # Test App
    print("--- App ---")
    row_0_app = df_app[df_app['label'] == 0].iloc[0]
    row_1_app = df_app[df_app['label'] == 1].iloc[0]
    print(f"Normal (L0): {score_app_session(row_0_app.to_dict())}")
    print(f"Fraud (L1): {score_app_session(row_1_app.to_dict())}")
    
    # Test USSD
    print("\n--- USSD ---")
    row_0_ussd = df_ussd[df_ussd['label'] == 0].iloc[0]
    row_1_ussd = df_ussd[df_ussd['label'] == 1].iloc[0]
    print(f"Normal (L0): {score_ussd_session(row_0_ussd.to_dict())}")
    print(f"Fraud (L1): {score_ussd_session(row_1_ussd.to_dict())}")
    
    # Tally USSD
    from collections import Counter
    fraud_rows = df_ussd[df_ussd['label'] == 1].head(20)
    feature_counts = Counter()
    for _, row in fraud_rows.iterrows():
        res = score_ussd_session(row.to_dict())
        for f_name, _ in res['top_features']:
            feature_counts[f_name] += 1
            
    model_ussd = joblib.load('models/ussd_model.pkl')
    print("\nFeature appearance counts (USSD, 20 fraud rows):")
    for i, f in enumerate(ussd_features):
        print(f"{f}: {feature_counts.get(f, 0)} (Importances: {model_ussd.feature_importances_[i]:.4f})")
