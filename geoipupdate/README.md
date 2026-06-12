# geoipupdate

Simple image to download/update a MaxMind GeoIP database.

## Setup

```sh
podman run \
    --rm --name geoipdate \
    -v /somewhere/GeoIP.conf:/etc/geoip/GeoIP.conf:ro \
    -v /somewhere/geoip:/usr/local/share/GeoIP \
    -it geoipupdate
```
