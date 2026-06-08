FROM docker.io/library/httpd:2.4.67
LABEL org.opencontainers.image.source=https://github.com/kiwix/minibrain

# TARGETPLATFORM is injected by docker build
ARG TARGETPLATFORM

ENV LIBMAXMINDDB_VERSION=1.13.3
ENV MOD_MAXMINDDB_VERSION=1.3.0
ENV GEOIPUPDATE_VERSION=7.1.1

RUN \
  groupadd -r mirrorbrain \
  && useradd -r -g mirrorbrain -s /bin/bash -c "MirrorBrain user" mirrorbrain \
  && mkdir -p /var/log/mirrorbrain/ \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
    rsync \
    curl automake libtool unzip build-essential libz-dev \
    libaprutil1-dev libaprutil1-dbd-pgsql \
    postgresql-client \
  && true

# GeoIP
RUN \
  cd /tmp \
  && mkdir -p /src/ \
  && curl -L -s -o libmaxminddb-${LIBMAXMINDDB_VERSION}.tar.gz https://github.com/maxmind/libmaxminddb/releases/download/${LIBMAXMINDDB_VERSION}/libmaxminddb-${LIBMAXMINDDB_VERSION}.tar.gz \
  && tar xzf libmaxminddb-${LIBMAXMINDDB_VERSION}.tar.gz -C /src \
  && rm libmaxminddb-${LIBMAXMINDDB_VERSION}.tar.gz \
  && cd /src/libmaxminddb-${LIBMAXMINDDB_VERSION} \
  && ./configure \
  && make \
  && make check \
  && make install \
  && ldconfig

RUN \
  echo "TARGETPLATFORM: $TARGETPLATFORM" \
    && if [ "$TARGETPLATFORM" = "linux/arm64/v8" \
        -o "$TARGETPLATFORM" = "linux/arm64" ]; then GEOIPUPDATE_ARCH="arm64"; \
       elif [ "$TARGETPLATFORM" = "linux/amd64/v3" \
        -o "$TARGETPLATFORM" = "linux/amd64/v2" \
        -o "$TARGETPLATFORM" = "linux/amd64" ]; then GEOIPUPDATE_ARCH="amd64"; \
       # we dont suppot any other arch so let it fail
       else GEOIPUPDATE_ARCH="unknown"; fi \
  && cd /tmp \
  && curl -v -L -o geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}.tar.gz https://github.com/maxmind/geoipupdate/releases/download/v${GEOIPUPDATE_VERSION}/geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}.tar.gz \
  && tar -xf geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}.tar.gz \
  && mv geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}/geoipupdate /usr/bin/geoipupdate \
  && rm /tmp/geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}.tar.gz \
  && rm -rf ./geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}/

COPY conf/httpd.conf /usr/local/apache2/httpd.conf
COPY conf/vhost.conf /usr/local/apache2/extra/httpd-vhosts.conf
COPY conf/mirrorbrain.conf /etc/mirrorbrain.conf

RUN \
  cd /tmp \
  && curl -L -s -o mod_maxminddb-${MOD_MAXMINDDB_VERSION}.tar.gz https://github.com/maxmind/mod_maxminddb/releases/download/${MOD_MAXMINDDB_VERSION}/mod_maxminddb-${MOD_MAXMINDDB_VERSION}.tar.gz \
  && tar xzf mod_maxminddb-${MOD_MAXMINDDB_VERSION}.tar.gz -C /src \
  && rm mod_maxminddb-${MOD_MAXMINDDB_VERSION}.tar.gz \
  && cd /src/mod_maxminddb-${MOD_MAXMINDDB_VERSION} \
  && ./configure \
  && make install

COPY mod_autoindex_mb/ /src/mod_autoindex_mb/
COPY mod_mirrorbrain/ /src/mod_mirrorbrain/

RUN \
  cd /src/mod_mirrorbrain \
  && curl -s -L -O http://apache.webthing.com/svn/apache/forms/mod_form.h \
  && curl -s -L -O http://apache.webthing.com/svn/apache/forms/mod_form.c \
  && apxs -cia -lm mod_form.c \
  && apxs -e -n dbd -a modules/mod_dbd.so \
  && apxs -e -n rewrite -a modules/mod_rewrite.so \
  && apxs -cia -lm mod_mirrorbrain.c \
  && cd ../mod_autoindex_mb \
  && apxs -cia mod_autoindex_mb.c \
  && true

CMD ["/usr/bin/httpd-foreground", "-DUseMaxMind"]
