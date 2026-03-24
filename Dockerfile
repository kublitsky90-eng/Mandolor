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
    chmod +x swgoh-comlink-4.1.0 && \
    echo "✅ Comlink установлен" && \
    ls -la

# Устанавливаем Python зависимости
RUN pip install python-telegram-bot requests

# Копируем код бота
COPY bot.py .

# Создаем простой скрипт запуска
RUN echo '#!/bin/sh\n\
echo "=== НАЧАЛО ЗАПУСКА ==="\n\
echo "Содержимое /app:"\n\
ls -la /app\n\
echo "=== ЗАПУСКАЕМ COMLINK ==="\n\
/app/swgoh-comlink-4.1.0 -n "MySwgohBot" -p 3000 2>&1 &\n\
COMLINK_PID=$!\n\
echo "Comlink запущен с PID: $COMLINK_PID"\n\
echo "Ожидание 30 секунд..."\n\
sleep 30\n\
echo "=== ЗАПУСКАЕМ БОТА ==="\n\
python /app/bot.py\n\
echo "=== БОТ ЗАВЕРШИЛ РАБОТУ ==="' > start.sh && chmod +x start.sh

EXPOSE 3000

CMD ["./start.sh"]