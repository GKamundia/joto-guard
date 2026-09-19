# The API, and the same image for the Telegram bot: both need the package and the configs.
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# Dependencies first, so editing the source does not reinstall them.
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-compile -e ".[api,bot]"

COPY config/ config/
COPY bot/ bot/
COPY data/raw/organiser/ data/raw/organiser/

# The pipelines write here; compose mounts a volume over it so the bot sees the same files.
RUN mkdir -p data/processed data/reference

EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
