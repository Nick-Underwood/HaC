FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "mcp[cli]>=1.22.0" \
    fastapi \
    uvicorn[standard] \
    httpx \
    pydantic \
    && pip cache purge

COPY server.py /app/server.py

CMD ["python", "-m", "server"]
