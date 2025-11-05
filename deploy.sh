#!/bin/bash
# try catch in bash
{
  # Start all services defined in the docker-compose files
  docker-compose -f ./infra/nginx/docker-compose.yml up -d
  sleep 5
  docker-compose -f infra/monitoring/docker-compose.yml up -d
  sleep 5
  docker-compose -f ./data-pipeline/docker-compose.yml up -d
  sleep 5
  docker-compose -f AI\\ML/docker-compose.yml up -d
} || {
    ./down.sh
}
