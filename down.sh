#!/bin/bash
# Stop and remove all containers defined in the docker-compose files
docker-compose -f ./AI\\ML/docker-compose.yml down
docker-compose -f ./data-pipeline/docker-compose.yml down
docker-compose -f ./infra/monitoring/docker-compose.yml down
docker-compose -f ./infra/nginx/docker-compose.yml down 
