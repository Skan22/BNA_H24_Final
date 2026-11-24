FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --extra postgres
COPY contracts ./contracts
COPY engine ./engine
COPY api ./api
COPY services ./services
COPY kit ./kit
COPY eval ./eval
COPY tools ./tools
ENV PATH="/app/.venv/bin:$PATH" BOUSSOLA_LLM=none
# Les rapports de mesure (page /jury) sont recalculés à la construction : aucun fichier généré n'est requis dans le dépôt.
RUN python eval/run.py --split public --seuil-top1 0.90 && python eval/run.py --split private --seuil-top1 0.90
RUN useradd --uid 10001 --create-home boussola && chown boussola /app
USER boussola
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
