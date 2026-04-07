FROM python:3.11-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app


FROM base AS build-stage

RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip wheel \
    && python -m pip wheel --no-cache-dir --wheel-dir /wheels \
    -r /app/requirements.txt


FROM base AS runtime-deps-stage

RUN apt-get update && apt-get install --no-install-recommends -y \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build-stage /wheels /wheels
COPY --from=build-stage /app/requirements.txt /app/requirements.txt

RUN python -m pip install --no-index --find-links=/wheels \
    -r /app/requirements.txt \
    && rm -rf /wheels /app/requirements.txt


FROM runtime-deps-stage AS run-stage

RUN addgroup --gid 10001 --system django && \
    adduser --no-create-home --shell /bin/false \
    --disabled-password --uid 10001 --system --group django

COPY --chown=django:django ./src/ /app/

COPY --chown=django:django ./docker/django/entrypoint.sh /entrypoint.sh
RUN sed -i "s/\r$//g" /entrypoint.sh

COPY --chown=django:django ./docker/django/start-web.sh /start-web.sh
RUN sed -i "s/\r$//g" /start-web.sh

COPY --chown=django:django ./docker/django/start-web-dev.sh /start-web-dev.sh
RUN sed -i "s/\r$//g" /start-web-dev.sh

RUN chmod 555 /entrypoint.sh /start-web.sh /start-web-dev.sh

RUN mkdir -p /tmp/prometheus_multiproc && \
    chown django:django /tmp/prometheus_multiproc && \
    chmod 755 /tmp/prometheus_multiproc

USER django

ENTRYPOINT ["/entrypoint.sh"]

CMD ["/start-web.sh"]