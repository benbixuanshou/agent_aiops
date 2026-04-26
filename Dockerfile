FROM python:3.12-slim
WORKDIR /app

RUN pip install --no-cache-dir "poetry<2.0"

COPY pyproject.toml ./
RUN poetry install --no-dev --no-root

COPY . .

EXPOSE 9900
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9900"]
