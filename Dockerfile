FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    wget \
    tar \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN wget https://github.com/swgoh-utils/swgoh-comlink/releases/download/v4.1.0/swgoh-comlink-linux-4.1.0.tgz -O comlink.tgz && \
    tar -xzf comlink.tgz && \
    rm comlink.tgz && \
    chmod +x swgoh-comlink

RUN pip install python-telegram-bot requests

COPY bot.py .

RUN echo '#!/bin/sh\n\
./swgoh-comlink -n "MySwgohBot" -p 3000 &\n\
sleep 5\n\
python bot.py' > start.sh && chmod +x start.sh

EXPOSE 3000

CMD ["./start.sh"]