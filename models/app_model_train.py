import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

# Load data
data_path = 'data/app_channel_data.csv'
df = pd.read_csv(data_path)

# Features and target
features = ['typing_speed_deviation', 'pasted_char_ratio', 'first_action_deviation', 'amount_deviation']
target = 'label'

# Validate NaNs
if df[features + [target]].isnull().values.any():
    print("WARNING: NaNs found in dataset.")
    exit(1)

X = df[features]
y = df[target]

# Split data
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(gss.split(X, y, groups=df['user_id']))
X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

# Train model
clf = RandomForestClassifier(class_weight='balanced', random_state=42)
clf.fit(X_train, y_train)

# Save model
os.makedirs('models', exist_ok=True)
joblib.dump(clf, 'models/app_model.pkl')

# Predictions
y_pred = clf.predict(X_test)

# Print requirements
train_users = set(X_train.index.map(lambda i: df.loc[i, 'user_id']))
test_users = set(X_test.index.map(lambda i: df.loc[i, 'user_id']))
print(f"Zero user_ids overlap between train and test: {len(train_users & test_users) == 0}")
print(y_train.value_counts())
print(y_test.value_counts())
print("RandomForestClassifier(class_weight='balanced', random_state=42)")
print(classification_report(y_test, y_pred))
print(confusion_matrix(y_test, y_pred))
