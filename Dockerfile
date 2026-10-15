FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY polya ./polya
COPY puzzleops ./puzzleops
COPY deploy/server.py deploy/requirements.txt ./deploy/
RUN pip install --no-cache-dir '.[imaging,solvers,learning]' -r deploy/requirements.txt \
    && useradd --create-home polya
USER polya
EXPOSE 10000
CMD ["python", "deploy/server.py"]
