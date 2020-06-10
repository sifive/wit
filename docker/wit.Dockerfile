FROM python:3.8-alpine

COPY ./lib /wit/
WORKDIR /wit

RUN apk add git --no-cache && \
    python3 -m pip install .

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

CMD /bin/sh
