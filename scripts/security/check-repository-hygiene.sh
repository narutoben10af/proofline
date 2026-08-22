#!/usr/bin/env bash
set -euo pipefail

failures=0

fail() {
  printf 'security baseline: %s\n' "$1" >&2
  failures=$((failures + 1))
}

while IFS= read -r -d '' path; do
  name=${path##*/}
  lower_name=$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')

  case "$lower_name" in
    .env|.env.*)
      if [[ "$lower_name" != ".env.example" ]]; then
        fail "tracked environment file is forbidden: $path"
      fi
      ;;
    *.pem|*.key|*.p12|*.pfx)
      fail "tracked private-key or certificate bundle is forbidden: $path"
      ;;
    *.pdf)
      fail "tracked PDF requires a separately reviewed reuse decision: $path"
      ;;
    *.xlsm|*.xltm|*.docm|*.dotm|*.pptm|*.potm)
      fail "tracked macro-enabled Office document is forbidden: $path"
      ;;
  esac
done < <(git ls-files -z)

if [[ -f .env.example ]] && grep -nE '^[A-Za-z_][A-Za-z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)=[^[:space:]#]+' .env.example; then
  fail '.env.example must contain empty or clearly non-secret values for secret-like variables'
fi

if git grep -nI -E '(AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[0-9A-Za-z]{30,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' -- . \
  ':(exclude)docs/security/review-checklist.md' \
  ':(exclude)scripts/security/check-repository-hygiene.sh'; then
  fail 'a high-confidence credential pattern appears in tracked content'
fi

if [[ -f package.json ]] && [[ ! -f pnpm-lock.yaml && ! -f package-lock.json && ! -f yarn.lock ]]; then
  fail 'package.json must be committed with exactly one supported JavaScript lockfile'
fi

if [[ -f pyproject.toml ]] && [[ ! -f uv.lock && ! -f poetry.lock && ! -f pdm.lock ]]; then
  fail 'pyproject.toml must be committed with the selected Python lockfile'
fi

if (( failures > 0 )); then
  printf 'security baseline: %d check(s) failed\n' "$failures" >&2
  exit 1
fi

printf 'security baseline: repository hygiene checks passed\n'
