FROM python:3.12-alpine

WORKDIR /gateway
COPY server.py ./server.py

USER 65532:65532

EXPOSE 8080

CMD ["python", "server.py"]
