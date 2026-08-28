FROM python:3.12-alpine

RUN apk add --no-cache openssl

WORKDIR /mock
COPY server.py ./server.py

EXPOSE 8443

CMD ["python", "server.py"]
