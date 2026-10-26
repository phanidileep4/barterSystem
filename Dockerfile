# BarterSystem proof of concept. Build from the repository root:
#   docker build -t barter-poc . && docker run -p 8080:8080 barter-poc
FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.13.1
WORKDIR /app
COPY prototype ./prototype
COPY poc ./poc
WORKDIR /app/poc
RUN uv sync --frozen --no-dev --extra claude

# SQLite lives on the container's disk: a fresh instance re-seeds the demo.
ENV HOST=0.0.0.0 PORT=8080 BARTER_DB=/tmp/barter-poc.sqlite3
EXPOSE 8080
CMD ["uv", "run", "--frozen", "--no-sync", "barter-poc"]
