FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','8080') + '/health')" || exit 1

CMD ["python", "main.py"]
