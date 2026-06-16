#!/bin/sh
# ILM bootstrap — applies a 14-day delete policy to all security-logs-* indices.
# Runs once as an init container after Elasticsearch is healthy.
set -e
ES_URL="http://elasticsearch:9200"

echo "[ILM] Applying lifecycle policy to Elasticsearch..."

curl -sf -X PUT "$ES_URL/_ilm/policy/securewatch-14d" \
  -H "Content-Type: application/json" \
  -d '{
    "policy": {
      "phases": {
        "delete": {
          "min_age": "14d",
          "actions": { "delete": {} }
        }
      }
    }
  }'
echo ""
echo "[ILM] Policy 'securewatch-14d' created (delete after 14 days)."

curl -sf -X PUT "$ES_URL/_index_template/securewatch-logs-template" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["security-logs-*"],
    "template": {
      "settings": {
        "index.lifecycle.name": "securewatch-14d",
        "number_of_shards": 1,
        "number_of_replicas": 0
      }
    },
    "priority": 100
  }'
echo ""
echo "[ILM] Index template applied to security-logs-* (1 shard, 0 replicas, lifecycle=securewatch-14d)."
echo "[ILM] Setup complete — indices older than 14 days will be auto-deleted."
