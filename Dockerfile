FROM node:20-alpine AS frontend

WORKDIR /build
COPY search-ui/frontend/package.json search-ui/frontend/package-lock.json* ./
RUN npm ci
COPY search-ui/frontend/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml setup.cfg* setup.py* ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

COPY search-ui/backend/requirements.txt /app/search-ui/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/search-ui/backend/requirements.txt

COPY search-ui/backend/ /app/search-ui/backend/

COPY --from=frontend /build/dist/ /app/search-ui/frontend/dist/

EXPOSE 8000

WORKDIR /app/search-ui/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
