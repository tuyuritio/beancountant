FROM python:3.14.4-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	bison \
	flex \
	libsqlite3-dev \
    libblas3 \
    liblapack3 \
	&& rm -rf /var/lib/apt/lists/*

RUN pip install --prefix=/install beancount


FROM python:3.14.4-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "app.main"]
