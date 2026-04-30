FROM python:3.14.4-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	bison \
	flex \
	libsqlite3-dev \
    libblas3 \
    liblapack3 \
	&& rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir beancount

FROM python:3.14.4-slim

RUN useradd --create-home appuser

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-0 \
    libblas3 \
    liblapack3 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER appuser

CMD ["python", "-m", "app.main"]
