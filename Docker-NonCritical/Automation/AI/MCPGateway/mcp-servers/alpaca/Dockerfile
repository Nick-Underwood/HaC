FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir alpaca-mcp-server==2.3.2

EXPOSE 3000

ENTRYPOINT ["alpaca-mcp-server"]
CMD ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "3000"]
