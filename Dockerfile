FROM python:3.11-slim

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential libffi-dev && rm -rf /var/lib/apt/lists/*

# copy requirements first to leverage cache
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# copy project
COPY . /app

# ensure logs dir exists
RUN mkdir -p /app/logs

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
