FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=5

WORKDIR /app

# Python dependencies change far less often than application code. Keeping this
# layer separate lets Docker reuse it during normal backend iterations.
COPY pyproject.toml ./

RUN python -c "import tomllib; from pathlib import Path; dependencies = tomllib.loads(Path('pyproject.toml').read_text())['project']['dependencies']; Path('/tmp/requirements.txt').write_text('\\n'.join(dependencies))" \
    && python -m pip install --no-cache-dir --timeout 180 --retries 5 -r /tmp/requirements.txt \
    && useradd --create-home --uid 10001 appuser

COPY . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "knowledgeops.api:app", "--host", "0.0.0.0", "--port", "8000"]
