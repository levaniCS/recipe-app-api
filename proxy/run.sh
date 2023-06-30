#!/bin/sh

set -e

# We are inserting content of 'default.conf.tpl' file inside 'default.conf'
envsubst < /etc/nginx/default.conf.tpl > /etc/nginx/conf.d/default.conf
nginx -g 'daemon off;'
