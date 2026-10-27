#!/usr/bin/env bash
set -euo pipefail

image="${1:-ai-cad-generator}"
container="ai-cad-generator-smoke"
response_file="$(mktemp)"
archive_file="$(mktemp --suffix=.zip)"
plan_file="$(mktemp)"
generate_request_file="$(mktemp)"

cleanup() {
  docker logs "$container" || true
  docker rm -f "$container" >/dev/null 2>&1 || true
  rm -f "$response_file" "$archive_file" "$plan_file" "$generate_request_file"
}
trap cleanup EXIT

docker run -d --name "$container" -p 127.0.0.1:7860:7860 "$image"
ready=0
for attempt in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:7860/health >/dev/null; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  echo "::error::Application did not become healthy within 120 seconds"
  exit 1
fi

curl -fsS http://127.0.0.1:7860/api/health/cad
plan_status="$(curl -sS -w '%{http_code}' -o "$plan_file" \
  -X POST http://127.0.0.1:7860/api/plan \
  -H 'Content-Type: application/json' \
  -d '{"description":"Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm, rãnh xuyên dài 30 mm rộng 8 mm ở giữa tấm theo chiều dài","part_name":"ci_plate"}')"
if [ "$plan_status" != "200" ]; then
  echo "::error::POST /api/plan returned HTTP $plan_status"
  cat "$plan_file"
  exit 1
fi
python -c 'import json,sys; print(json.dumps({"plan": json.load(sys.stdin)["plan"]}))' \
  < "$plan_file" > "$generate_request_file"
status="$(curl -sS -w '%{http_code}' -o "$response_file" \
  -X POST http://127.0.0.1:7860/api/generate \
  -H 'Content-Type: application/json' \
  --data-binary "@$generate_request_file")"
if [ "$status" != "200" ]; then
  echo "::error::POST /api/generate returned HTTP $status"
  echo "Response body:"
  cat "$response_file"
  exit 1
fi

mv "$response_file" "$archive_file"
python tests/validate_generated_archive.py "$archive_file"
