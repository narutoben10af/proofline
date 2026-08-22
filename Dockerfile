FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

RUN useradd --create-home --uid 10001 proofline
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

USER proofline
EXPOSE 8000
CMD ["sh", "-c", "uvicorn proofline.api:app --host 0.0.0.0 --port ${PORT}"]
