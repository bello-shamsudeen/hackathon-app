import pandas as pd
import joblib
import json
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import precision_score, recall_score, confusion_matrix, average_precision_score

df = pd.read_csv('data/app_channel_data.csv')
features = ['typing_speed_deviation', 'pasted_char_ratio', 'first_action_deviation', 'amount_deviation']
X = df[features]
y = df['label']

gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(gss.split(X, y, groups=df['user_id']))
X_test = X.iloc[test_idx]
y_test = y.iloc[test_idx]
print(f"Test set size: {len(y_test)}")
print(y_test.value_counts())

clf = joblib.load('models/app_model.pkl')
probs = clf.predict_proba(X_test)[:, 1]
y_pred = (probs >= 0.5).astype(int)

tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
pr = precision_score(y_test, y_pred)
rc = recall_score(y_test, y_pred)
fpr = fp / (fp + tn)
pr_auc = average_precision_score(y_test, probs)

metrics = {
    "precision": float(pr),
    "recall": float(rc),
    "false_positive_rate": float(fpr),
    "pr_auc": float(pr_auc),
    "threshold_used": 0.5,
    "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]]
}

with open('models/app_model_metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)

print(json.dumps(metrics, indent=2))