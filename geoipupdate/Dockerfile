FROM docker.io/library/alpine:3.24
LABEL org.opencontainers.image.source=https://github.com/kiwix/minibrain

# TARGETPLATFORM is injected by docker build
ARG TARGETPLATFORM

ENV GEOIPUPDATE_VERSION=7.1.1

RUN \
    echo "TARGETPLATFORM: $TARGETPLATFORM" \
    && if [ "$TARGETPLATFORM" = "linux/arm64/v8" \
        -o "$TARGETPLATFORM" = "linux/arm64" ]; then GEOIPUPDATE_ARCH="arm64"; \
       elif [ "$TARGETPLATFORM" = "linux/amd64/v3" \
        -o "$TARGETPLATFORM" = "linux/amd64/v2" \
        -o "$TARGETPLATFORM" = "linux/amd64" ]; then GEOIPUPDATE_ARCH="amd64"; \
       # we dont suppot any other arch so let it fail
       else GEOIPUPDATE_ARCH="unknown"; fi \
    && apk add --no-cache dumb-init curl \
    && cd /tmp/ \
    && curl -v -L -o geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}.tar.gz https://github.com/maxmind/geoipupdate/releases/download/v${GEOIPUPDATE_VERSION}/geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}.tar.gz \
    && tar -xf geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}.tar.gz \
    && mv geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}/geoipupdate /usr/bin/geoipupdate \
    && rm /tmp/geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}.tar.gz \
    && rm -rf ./geoipupdate_${GEOIPUPDATE_VERSION}_linux_${GEOIPUPDATE_ARCH}/ \
    && mkdir -p /usr/local/share/GeoIP /etc/geoip \
    && printf "\
# GeoIP.conf file for `geoipupdate` program, for versions >= 3.1.1.\n\
# Used to update GeoIP databases from https://www.maxmind.com.\n\
# For more information about this config file, visit the docs at\n\
# https://dev.maxmind.com/geoip/updating-databases.\n\
\n\
# `AccountID` is from your MaxMind account.\n\
AccountID 000000\n\
\n\
# `LicenseKey` is from your MaxMind account.\n\
LicenseKey xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n\
\n\
# `EditionIDs` is from your MaxMind account.\n\
EditionIDs GeoLite2-ASN GeoLite2-City GeoLite2-Country\n\
" > /etc/geoip/GeoIP.conf

VOLUME /usr/local/share/GeoIP

CMD ["/usr/bin/geoipupdate", "-f", "/etc/geoip/GeoIP.conf", "-v"]
