import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

# Load data
data_path = 'data/ussd_channel_data.csv'
df = pd.read_csv(data_path)

# Features and target
features = ['amount_deviation', 'time_of_day_deviation', 'session_retry_deviation', 'sim_swap_risk']
target = 'label'

# Validate NaNs
if df[features + [target]].isnull().values.any():
    print("WARNING: NaNs found in dataset.")
    exit(1)

X = df[features]
y = df[target]

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Train model
clf = RandomForestClassifier(class_weight='balanced', random_state=42)
clf.fit(X_train, y_train)

# Save model
os.makedirs('models', exist_ok=True)
joblib.dump(clf, 'models/ussd_model.pkl')

# Predictions
y_pred = clf.predict(X_test)

# Print requirements
print(y_train.value_counts())
print(y_test.value_counts())
print("RandomForestClassifier(class_weight='balanced', random_state=42)")
print(classification_report(y_test, y_pred))
print(confusion_matrix(y_test, y_pred))
