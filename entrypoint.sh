#!/bin/sh

/bin/cat /etc/motd

export PATH="/usr/local/mbenv/bin:${PATH}"

exec "$@"
