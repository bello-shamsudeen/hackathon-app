FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
# Division 4/6 pull in scikit-learn / xgboost / scipy / shap / numba — a lot of
# large wheels. On a flaky link a fresh download often times out partway; the
# BuildKit cache mount below keeps already-downloaded wheels between build
# attempts so a retry resumes instead of starting over (hence NO --no-cache-dir).
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 10 -r requirements.txt

COPY . .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
