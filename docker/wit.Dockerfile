FROM python:3.8-alpine

COPY ./lib /wit/
WORKDIR /wit

RUN apk add git --no-cache && \
    python3 -m pip install .

CMD /bin/sh
