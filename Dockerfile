FROM python:3.10-slim-bookworm

RUN apt-get update && apt-get install --no-install-recommends -y \
    pandoc \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

RUN pip install --no-cache-dir pypandoc requests pillow

COPY convert.py /app/convert.py

WORKDIR /data

ENTRYPOINT ["python", "/app/convert.py"]
