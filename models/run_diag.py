import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

df = pd.read_csv('data/app_channel_data.csv')
features = ['typing_speed_deviation', 'pasted_char_ratio', 'first_action_deviation', 'amount_deviation']
target = 'label'

X = df[features]
y = df[target]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

model = joblib.load('models/app_model.pkl')
y_pred = model.predict(X_test)

output = []
output.append("train_test_split line:")
output.append("X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)")
output.append("")
output.append("classification_report:")
output.append(classification_report(y_test, y_pred))
output.append("confusion_matrix:")
output.append(str(confusion_matrix(y_test, y_pred)))

with open('models/run_diag_output.txt', 'w') as f:
    f.write('\n'.join(output))

print('\n'.join(output))