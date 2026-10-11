# Dash app container (Hugging Face Spaces, Render or any Docker host).
FROM python:3.12-slim
WORKDIR /app
COPY requirements-dash.txt .
RUN pip install --no-cache-dir -r requirements-dash.txt
COPY dash_app.py figures.py ./
COPY dashapp/ dashapp/
COPY pipeline/__init__.py pipeline/insights.py pipeline/
COPY config/settings.yaml config/
COPY data/processed/ data/processed/
# Hugging Face Spaces expects port 7860; Render sets $PORT itself.
ENV PORT=7860
EXPOSE 7860
CMD gunicorn dash_app:server --bind 0.0.0.0:${PORT} --workers 2 --timeout 120
