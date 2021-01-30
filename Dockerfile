FROM python:3.9.1-alpine3.12
COPY requirements.txt dht22mqtt.py gpiomapping.py ./
RUN apk add gcc musl-dev && \
    pip3 install -r requirements.txt --no-cache-dir && \
    pip3 cache purge && \
    apk del gcc musl-dev && \
    rm -rf /var/lib/apk/lists/*
CMD [ "python3", "-u", "dht22mqtt.py" ]