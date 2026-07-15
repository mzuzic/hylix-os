FROM python:3.12-slim
WORKDIR /app

# System libraries WeasyPrint needs to render PDFs (pango/cairo/gdk-pixbuf) + fonts.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2 \
      libgdk-pixbuf-2.0-0 libffi8 shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
ENV SALES_OS_DB=/data/sales_os.db
VOLUME /data
EXPOSE 8000
CMD ["python", "server.py"]
