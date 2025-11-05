#!/usr/bin/env bash
# wait-for-it.sh: block until a host:port is available

set -e

HOST=$1
PORT=$2
shift 2
CMD="$@"

echo "[wait-for-it] Waiting for $HOST:$PORT..."

while ! nc -z $HOST $PORT; do
  sleep 2
done

echo "[wait-for-it] $HOST:$PORT is up - executing command"
exec $CMD
