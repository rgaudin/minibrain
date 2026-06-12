FROM python:3.14-alpine
LABEL org.opencontainers.image.source=https://github.com/kiwix/minibrain

# default location for config
ENV MIRRORBRAIN_CONFIG_FILE=/etc/mirrorbrain.conf
# run /etc/profile on shells (displays out motd)
ENV ENV="/etc/profile"

RUN \
    apk add --no-cache dumb-init python3 \
    rsync \
    # python dependencies
    && python3 -m venv /usr/local/mbenv \
    && /usr/local/mbenv/bin/pip3 install --no-cache-dir -U pip

# Copy pyproject.toml and its dependencies
COPY pyproject.toml README.md /src/
COPY src/minibrain/__about__.py /src/src/minibrain/__about__.py

# Install Python dependencies
RUN /usr/local/mbenv/bin/pip install --no-cache-dir /src

# Copy code + associated artifacts
COPY src /src/src
COPY *.md /src/
COPY server/conf/mirrorbrain.conf /etc/mirrorbrain.conf
COPY motd /etc/motd

# Install + cleanup
RUN \
    /usr/local/mbenv/bin/pip install --no-cache-dir /src \
    && rm -rf /src \
    && printf "\
export PATH=\"/usr/local/mbenv/bin:${PATH}\"\n\
/bin/cat /etc/motd\n\
" >> /etc/profile

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/sh"]
