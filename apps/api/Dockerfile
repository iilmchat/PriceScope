FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/viewer ./apps/viewer

RUN pip install --no-cache-dir .
ENV PRICESCOPE_MODE=local PRICESCOPE_HOST=0.0.0.0 PRICESCOPE_PORT=8765
EXPOSE 8765
CMD ["pricescope", "serve", "--local"]
