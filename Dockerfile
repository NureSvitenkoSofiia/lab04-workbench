FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project || pip install --no-cache-dir \
    "google-adk>=2.12.0,<3.0.0" chromadb python-frontmatter python-dotenv streamlit pandas pydantic

COPY app ./app
COPY kb ./kb
COPY workbench ./workbench
COPY streamlit_app.py ./
COPY .streamlit ./.streamlit

RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /vault /chroma_data /data \
    && chown -R appuser:appuser /app /vault /chroma_data /data

USER appuser

ENV KB_VAULT_PATH=/vault \
    CHROMA_PERSIST_DIR=/chroma_data \
    WORKBENCH_DB=/data/workbench.db

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
