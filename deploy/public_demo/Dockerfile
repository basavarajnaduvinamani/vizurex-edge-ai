FROM python:3.11-slim
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir -r requirements.txt
COPY --chown=user app.py index.html README.md LICENSE NOTICE ./
COPY --chown=user src ./src
USER user
ENV HOME=/home/user TORCH_HOME=/home/user/.cache/torch
EXPOSE 7860
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","7860","--workers","1","--limit-concurrency","4","--no-access-log"]
