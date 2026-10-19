FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OLLAMA_URL=http://host.docker.internal:11434

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY crew_pdf_4agents.py mcp_server.py ./

CMD ["python", "-u", "crew_pdf_4agents.py"]
