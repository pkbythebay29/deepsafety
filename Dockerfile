FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE MANIFEST.in /app/
COPY deepsafety /app/deepsafety

RUN python -m pip install --upgrade pip && \
    python -m pip install .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "deepsafety.api:app", "--host", "0.0.0.0", "--port", "8000"]
