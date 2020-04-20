FROM python:3.8-alpine

# Since we have no python deps outside the standard library,
# just copy in the python files we need
COPY ./lib/wit/*.py /wit/lib/wit/

RUN apk add git --no-cache                    && \
    echo exec python3 -m wit '$@' > /bin/wit  && \
    chmod +x /bin/wit

ENV PYTHONPATH=/wit/lib:$PYTHONPATH

CMD /bin/sh
