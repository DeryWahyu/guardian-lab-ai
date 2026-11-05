FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GUARDIAN_ML_MODE=shadow \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

COPY ml/pyproject.toml ./ml/pyproject.toml
COPY ml/src ./ml/src
RUN python -m pip install --no-cache-dir -e "./ml[serve]"

# Preserve every relative source path checked by the frozen runtime manifest.
COPY ml/policies ./ml/policies
COPY ml/provenance ./ml/provenance
COPY ml/reports/data-improvement-v6.json ./ml/reports/data-improvement-v6.json
COPY scripts/install_v6_model.py ./scripts/install_v6_model.py
RUN python scripts/install_v6_model.py

COPY docker/healthcheck.py ./docker/healthcheck.py
RUN useradd --system --uid 10001 --no-create-home guardian && \
    chown -R guardian:guardian /app/ml/runs
USER guardian

EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
  CMD ["python", "docker/healthcheck.py"]
CMD ["python", "-m", "uvicorn", "guardian_ml.shadow_service:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--limit-concurrency", "16", "--no-access-log"]
