FROM ubuntu:xenial AS build

RUN apt-get update && apt-get install -y \
    git \
    make \
    python3-pip

COPY . /wit/
WORKDIR /wit
RUN make install install_dir=/opt/sifive/wit

# Actual image build
FROM ubuntu:xenial

WORKDIR /root/

RUN apt-get update && apt-get install -y \
   git \
   openjdk-8-jdk \
   software-properties-common

COPY --from=build /opt/sifive/wit/ /opt/sifive/wit/
ENV PATH=$PATH:/opt/sifive/wit

CMD bash
