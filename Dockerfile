FROM python:3.14-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

RUN python3 -c "import tomllib,sys; d=tomllib.load(open('pyproject.toml','rb')); sys.stdout.write('\n'.join(d['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

COPY apps/ apps/
COPY libs/ libs/
RUN pip install --no-cache-dir --no-deps --prefix=/install .

FROM python:3.14-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

EXPOSE 8000

ENTRYPOINT ["sh", "-c"]
CMD ["uvicorn apps.api.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
