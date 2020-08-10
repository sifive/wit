# Note: This version should be changed when releasing new versions of Wit.
FROM sifive/wit:v0.13.2

RUN apk add bash --no-cache

COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
