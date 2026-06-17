FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOST=0.0.0.0
ENV APP_PORT=5000

WORKDIR /app

RUN apt-get update && \
    apt-get install --no-install-recommends -y ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN mkdir -p models && \
    curl -fL --retry 3 --retry-delay 5 \
      https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt \
      -o models/sam2.1_hiera_large.pt

COPY . .

RUN mkdir -p models && \
    cp sam2/configs/sam2.1/sam2.1_hiera_l.yaml models/sam2.1_hiera_l.yaml

EXPOSE 5000

CMD ["python", "app.py"]
