# Aura headless — VPS / server image
# Runs the 82-command CLI and the agent fleet without a display.
#
#   docker build -t aura .
#   docker run -it -v aura-data:/root/.aura aura --help
#   docker run -it -v aura-data:/root/.aura aura repl

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && apt-get clean

WORKDIR /app

COPY requirements-headless.txt .
RUN pip install --no-cache-dir -r requirements-headless.txt

COPY . .

# Lead scraping inside the container needs Chromium
RUN python -m playwright install --with-deps chromium || true

VOLUME ["/root/.aura"]

ENTRYPOINT ["python", "cli.py"]
CMD ["--help"]
