FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    wget \
    tar \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Скачиваем и распаковываем Comlink
RUN wget https://github.com/swgoh-utils/swgoh-comlink/releases/download/v4.1.0/swgoh-comlink-linux-4.1.0.tgz -O comlink.tgz && \
    tar -xzf comlink.tgz && \
    rm comlink.tgz && \
    chmod +x swgoh-comlink-4.1.0

# Устанавливаем Python зависимости
RUN pip install python-telegram-bot requests

# Копируем код бота
COPY bot.py .

# Создаем скрипт запуска — используем правильное имя файла
RUN echo '#!/bin/sh\n\
echo "🚀 Запускаем Comlink..."\n\
./swgoh-comlink-4.1.0 -n "MySwgohBot" -p 3000 &\n\
echo "⏳ Ожидаем запуск Comlink (15 секунд)..."\n\
sleep 15\n\
echo "✅ Запускаем Telegram бота..."\n\
python bot.py' > start.sh && chmod +x start.sh

EXPOSE 3000

CMD ["./start.sh"]