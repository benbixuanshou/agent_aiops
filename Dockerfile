FROM python:3.12-slim AS builder
WORKDIR /app

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir "poetry<2.0"

COPY pyproject.toml ./
RUN poetry source add --priority=default tsinghua https://pypi.tuna.tsinghua.edu.cn/simple || true && \
    poetry install --no-dev --no-root

FROM python:3.12-slim AS runtime
WORKDIR /app

RUN groupadd -r superbiz && useradd -r -g superbiz -d /app superbiz

COPY --from=builder /root/.cache/pypoetry /root/.cache/pypoetry
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

RUN chown -R superbiz:superbiz /app
USER superbiz

EXPOSE 9900
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9900"]
