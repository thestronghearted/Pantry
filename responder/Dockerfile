FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY app ./app
RUN useradd --system --uid 10001 responder && mkdir /reports && chown responder /reports
USER responder
EXPOSE 9000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/health')"
CMD ["uvicorn", "app.server:app_factory", "--factory", "--host", "0.0.0.0", "--port", "9000"]
