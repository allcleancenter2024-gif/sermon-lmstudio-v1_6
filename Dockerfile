FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERMON_USER_ROOT=/app

WORKDIR /app

# WeasyPrint is used for PDF export. ReportLab remains available as its fallback.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-pdf.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-pdf.txt

COPY app ./app
COPY static ./static
COPY templates ./templates
COPY fonts ./fonts
COPY VERSION.txt ./VERSION.txt

RUN mkdir -p /app/data /app/exports /app/backups

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
