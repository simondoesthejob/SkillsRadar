#!/usr/bin/env bash
# The same AWS resources the Terraform stacks create, built one AWS CLI call at a time.
#
# This is a learning aid: read it next to terraform/bootstrap, terraform/envs/dev and
# terraform/modules/ to see what each Terraform resource turns into. It is NOT a second way
# to deploy the project. Terraform keeps state and can show a plan, change and destroy things
# safely; this script does none of that.
#
# Safety:
#   * It uses a different name prefix (default "skillsradar-cli") so it never touches the
#     resources Terraform manages ("skillsradar-..."). Keep it that way.
#   * DRY_RUN=1 prints every command (and the JSON files they use) without calling AWS.
#   * It is not idempotent: re-running a step that already succeeded fails with "already exists".
#
# Usage:
#   GITHUB_REPO='owner@123/name@456' ./scripts/aws_cli_walkthrough.sh bootstrap
#   ./scripts/aws_cli_walkthrough.sh deploy
#   ./scripts/aws_cli_walkthrough.sh secrets          # prompts for the keys, nothing in history
#   ./scripts/aws_cli_walkthrough.sh run [source]     # source: adzuna | reed | hn_hiring
#   ./scripts/aws_cli_walkthrough.sh schedule on|off
#   ./scripts/aws_cli_walkthrough.sh status
#   ./scripts/aws_cli_walkthrough.sh teardown         # removes what "deploy" made
#   ./scripts/aws_cli_walkthrough.sh teardown-bootstrap
#
# Environment: AWS_REGION (default eu-west-2), PREFIX (default skillsradar-cli),
#              GITHUB_REPO (needed by "bootstrap"; the form that appears in the OIDC "sub"
#              claim, e.g. owner/name or owner@id/name@id), DRY_RUN=1.

set -euo pipefail

REGION="${AWS_REGION:-eu-west-2}"
PREFIX="${PREFIX:-skillsradar-cli}"
ENV_PREFIX="${PREFIX}-dev"
OIDC_HOST="token.actions.githubusercontent.com"
DRY_RUN="${DRY_RUN:-0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export AWS_DEFAULT_REGION="$REGION"

QUERIES="data scientist,machine learning engineer,data engineer,software engineer python,mlops"

# --- helpers ---------------------------------------------------------------------------------

# Run an aws command, or just print it (and any file:// JSON it uses) when DRY_RUN=1.
run() {
  printf '+ aws' >&2
  printf ' %q' "$@" >&2
  printf '\n' >&2
  if [ "$DRY_RUN" = 1 ]; then
    local a
    for a in "$@"; do
      if [[ "$a" == file://* ]]; then sed 's/^/    | /' "${a#file://}" >&2; fi
    done
    return 0
  fi
  aws "$@"
}

# Like run, but returns the command's output; in a dry run it returns the placeholder instead.
out() {
  local placeholder="$1"
  shift
  if [ "$DRY_RUN" = 1 ]; then
    printf '+ aws' >&2
    printf ' %q' "$@" >&2
    printf '   # -> %s\n' "$placeholder" >&2
    echo "$placeholder"
  else
    aws "$@"
  fi
}

# New IAM roles take a few seconds to become usable; retry a command that depends on one.
retry() {
  local tries=8 n=1
  until run "$@"; do
    if [ "$n" -ge "$tries" ]; then
      echo "giving up after $tries attempts" >&2
      return 1
    fi
    echo "  ...not ready yet (attempt $n of $tries), waiting 10s" >&2
    n=$((n + 1))
    sleep 10
  done
}

# Write JSON to a file under $WORK and print its file:// reference.
json() {
  local name="$1"
  cat >"$WORK/$name"
  echo "file://$WORK/$name"
}

account_id() {
  out 123456789012 sts get-caller-identity --query Account --output text
}

secure_bucket() { # name
  local b="$1"
  run s3api put-public-access-block --bucket "$b" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  run s3api put-bucket-versioning --bucket "$b" --versioning-configuration Status=Enabled
  run s3api put-bucket-encryption --bucket "$b" --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
}

make_bucket() { # name
  run s3api create-bucket --bucket "$1" --create-bucket-configuration "LocationConstraint=$REGION"
}

# Versioned buckets must have every version and delete marker removed before they can be deleted.
empty_bucket() { # name
  local b="$1" objs
  [ "$DRY_RUN" = 1 ] && {
    echo "+ (delete every object version and delete marker in $b)" >&2
    return 0
  }
  while :; do
    objs=$(aws s3api list-object-versions --bucket "$b" --max-items 1000 \
      --query '[Versions,DeleteMarkers][].{Key:Key,VersionId:VersionId}' --output json)
    if [ -z "$objs" ] || [ "$objs" = "null" ] || [ "$objs" = "[]" ]; then break; fi
    aws s3api delete-objects --bucket "$b" --delete "{\"Objects\":$objs,\"Quiet\":true}" >/dev/null
  done
}

# --- bootstrap: state bucket + GitHub OIDC roles (terraform/bootstrap, modules/github_oidc) --

cmd_bootstrap() {
  : "${GITHUB_REPO:?set GITHUB_REPO, e.g. owner/name (or the owner@id/name@id form from the OIDC sub claim)}"
  local acct state_bucket provider_arn
  acct=$(account_id)
  state_bucket="${PREFIX}-tfstate-${acct}"
  provider_arn="arn:aws:iam::${acct}:oidc-provider/${OIDC_HOST}"

  echo "== State bucket (aws_s3_bucket.state and its three settings)" >&2
  make_bucket "$state_bucket"
  secure_bucket "$state_bucket"

  echo "== GitHub OIDC provider (only one can exist per account)" >&2
  local existing="None"
  if [ "$DRY_RUN" != 1 ]; then
    existing=$(aws iam list-open-id-connect-providers \
      --query "OpenIDConnectProviderList[?ends_with(Arn, '/${OIDC_HOST}')] | [0].Arn" --output text)
  fi
  if [ "$existing" = "None" ]; then
    run iam create-open-id-connect-provider --url "https://${OIDC_HOST}" --client-id-list sts.amazonaws.com
  else
    echo "  already exists ($existing); reusing it" >&2
  fi

  trust_policy() { # sub claim
    json "trust-$1.json" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Federated": "${provider_arn}"},
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {"StringEquals": {
      "${OIDC_HOST}:aud": "sts.amazonaws.com",
      "${OIDC_HOST}:sub": "$2"
    }}
  }]
}
EOF
  }

  echo "== Plan role: assumable from pull requests, read-only plus the state bucket" >&2
  run iam create-role --role-name "${PREFIX}-github-plan" \
    --assume-role-policy-document "$(trust_policy plan "repo:${GITHUB_REPO}:pull_request")"
  run iam attach-role-policy --role-name "${PREFIX}-github-plan" \
    --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess
  run iam put-role-policy --role-name "${PREFIX}-github-plan" --policy-name terraform-state \
    --policy-document "$(json state-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "ReadWriteStateAndLockfile", "Effect": "Allow",
     "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
     "Resource": "arn:aws:s3:::${state_bucket}/*"},
    {"Sid": "ListStateBucket", "Effect": "Allow",
     "Action": "s3:ListBucket", "Resource": "arn:aws:s3:::${state_bucket}"}
  ]
}
EOF
)"

  echo "== Apply role: assumable only from jobs that use the 'dev' GitHub environment" >&2
  run iam create-role --role-name "${PREFIX}-github-apply" \
    --assume-role-policy-document "$(trust_policy apply "repo:${GITHUB_REPO}:environment:dev")"
  run iam attach-role-policy --role-name "${PREFIX}-github-apply" \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

  echo "Done. State bucket: ${state_bucket}" >&2
}

# --- deploy: buckets, secrets, queue, Lambda, schedule, alarm (terraform/envs/dev) ------------

schedule_args() { # state
  local acct="$1" state="$2"
  local fn_arn="arn:aws:lambda:${REGION}:${acct}:function:${ENV_PREFIX}-ingest"
  local role_arn="arn:aws:iam::${acct}:role/${ENV_PREFIX}-ingest-scheduler"
  local dlq_arn="arn:aws:sqs:${REGION}:${acct}:${ENV_PREFIX}-ingest-dlq"
  SCHEDULE_ARGS=(
    --name "${ENV_PREFIX}-ingest"
    --schedule-expression 'cron(0 6 * * ? *)'
    --schedule-expression-timezone Europe/London
    --state "$state"
    --flexible-time-window Mode=OFF
    --target "$(json "target-$state.json" <<EOF
{
  "Arn": "${fn_arn}",
  "RoleArn": "${role_arn}",
  "RetryPolicy": {"MaximumRetryAttempts": 2, "MaximumEventAgeInSeconds": 3600},
  "DeadLetterConfig": {"Arn": "${dlq_arn}"}
}
EOF
)"
  )
}

cmd_deploy() {
  local acct
  acct=$(account_id)
  local raw="${ENV_PREFIX}-raw-${acct}"
  local dlq_name="${ENV_PREFIX}-ingest-dlq"
  local dlq_arn="arn:aws:sqs:${REGION}:${acct}:${dlq_name}"
  local log_group="/aws/lambda/${ENV_PREFIX}-ingest"
  local fn="${ENV_PREFIX}-ingest"

  echo "== Data buckets (modules/data): raw, curated, artifacts" >&2
  local key b
  for key in raw curated artifacts; do
    b="${ENV_PREFIX}-${key}-${acct}"
    make_bucket "$b"
    secure_bucket "$b"
    run s3api put-bucket-lifecycle-configuration --bucket "$b" --lifecycle-configuration \
      "$(json lifecycle.json <<'EOF'
{"Rules": [{
  "ID": "housekeeping",
  "Status": "Enabled",
  "Filter": {},
  "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
  "NoncurrentVersionExpiration": {"NoncurrentDays": 30}
}]}
EOF
)"
  done

  echo "== Secrets Manager: empty containers, the values are stored later" >&2
  local adzuna_arn reed_arn
  adzuna_arn=$(out "arn:aws:secretsmanager:${REGION}:${acct}:secret:${ENV_PREFIX}/adzuna-AbCdEf" \
    secretsmanager create-secret --name "${ENV_PREFIX}/adzuna" \
    --description 'Adzuna API credentials as JSON: {"app_id": "...", "app_key": "..."}' \
    --query ARN --output text)
  reed_arn=$(out "arn:aws:secretsmanager:${REGION}:${acct}:secret:${ENV_PREFIX}/reed-AbCdEf" \
    secretsmanager create-secret --name "${ENV_PREFIX}/reed" \
    --description 'Reed Jobseeker API key as JSON: {"api_key": "..."}' \
    --query ARN --output text)

  echo "== Dead-letter queue and log group" >&2
  run sqs create-queue --queue-name "$dlq_name" \
    --attributes MessageRetentionPeriod=1209600,SqsManagedSseEnabled=true
  run logs create-log-group --log-group-name "$log_group"
  run logs put-retention-policy --log-group-name "$log_group" --retention-in-days 30

  echo "== Lambda execution role and its permissions" >&2
  run iam create-role --role-name "${ENV_PREFIX}-ingest-lambda" \
    --assume-role-policy-document "$(json lambda-trust.json <<'EOF'
{"Version": "2012-10-17", "Statement": [{
  "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
EOF
)"
  run iam put-role-policy --role-name "${ENV_PREFIX}-ingest-lambda" --policy-name ingest \
    --policy-document "$(json lambda-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "WriteRawData", "Effect": "Allow", "Action": "s3:PutObject",
     "Resource": "arn:aws:s3:::${raw}/raw/*"},
    {"Sid": "ReadApiCredentials", "Effect": "Allow", "Action": "secretsmanager:GetSecretValue",
     "Resource": ["${adzuna_arn}", "${reed_arn}"]},
    {"Sid": "DeadLetter", "Effect": "Allow", "Action": "sqs:SendMessage", "Resource": "${dlq_arn}"},
    {"Sid": "Logs", "Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
     "Resource": "arn:aws:logs:${REGION}:${acct}:log-group:${log_group}:*"}
  ]
}
EOF
)"

  echo "== Lambda function: package src/ and create it" >&2
  mkdir -p "$WORK/build"
  (cd "$ROOT/src" && zip -qr "$WORK/build/ingest.zip" . \
    -x '*__pycache__*' -x '*.pyc' -x '*.egg-info/*')
  retry lambda create-function --function-name "$fn" \
    --role "arn:aws:iam::${acct}:role/${ENV_PREFIX}-ingest-lambda" \
    --runtime python3.12 --handler skillsradar.handler.lambda_handler \
    --zip-file "fileb://$WORK/build/ingest.zip" --timeout 180 --memory-size 256 \
    --dead-letter-config "TargetArn=${dlq_arn}" \
    --environment "$(json lambda-env.json <<EOF
{"Variables": {
  "RAW_BUCKET": "${raw}",
  "ADZUNA_SECRET_ARN": "${adzuna_arn}",
  "ADZUNA_COUNTRY": "gb",
  "ADZUNA_QUERIES": "${QUERIES}",
  "REED_SECRET_ARN": "${reed_arn}",
  "REED_QUERIES": "${QUERIES}",
  "REED_LOCATION": ""
}}
EOF
)"

  echo "== Scheduler role, and the daily schedule (created DISABLED)" >&2
  run iam create-role --role-name "${ENV_PREFIX}-ingest-scheduler" \
    --assume-role-policy-document "$(json scheduler-trust.json <<'EOF'
{"Version": "2012-10-17", "Statement": [{
  "Effect": "Allow", "Principal": {"Service": "scheduler.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
EOF
)"
  run iam put-role-policy --role-name "${ENV_PREFIX}-ingest-scheduler" --policy-name invoke-ingest \
    --policy-document "$(json scheduler-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": "lambda:InvokeFunction",
     "Resource": "arn:aws:lambda:${REGION}:${acct}:function:${fn}"},
    {"Effect": "Allow", "Action": "sqs:SendMessage", "Resource": "${dlq_arn}"}
  ]
}
EOF
)"
  schedule_args "$acct" DISABLED
  retry scheduler create-schedule "${SCHEDULE_ARGS[@]}"

  echo "== CloudWatch alarm on the dead-letter queue" >&2
  run cloudwatch put-metric-alarm --alarm-name "${ENV_PREFIX}-ingest-dlq-not-empty" \
    --alarm-description 'A scheduled ingestion run failed and landed in the dead-letter queue.' \
    --namespace AWS/SQS --metric-name ApproximateNumberOfMessagesVisible \
    --dimensions "Name=QueueName,Value=${dlq_name}" --statistic Maximum --period 300 \
    --evaluation-periods 1 --threshold 0 --comparison-operator GreaterThanThreshold \
    --treat-missing-data notBreaching

  echo "Done. Next: '$0 secrets', then '$0 run reed'." >&2
}

# --- secrets, run, schedule, status ------------------------------------------------------------

cmd_secrets() {
  local app_id app_key reed_key
  if [ "$DRY_RUN" = 1 ]; then
    app_id='<app_id>' app_key='<app_key>' reed_key='<reed_key>'  # never echo real keys
  else
    read -r -p "Adzuna app_id: " app_id
    read -r -s -p "Adzuna app_key: " app_key
    echo
    read -r -s -p "Reed api_key: " reed_key
    echo
  fi
  # Values are built into JSON files, never put on the command line or in shell history.
  run secretsmanager put-secret-value --secret-id "${ENV_PREFIX}/adzuna" \
    --secret-string "$(json adzuna.json <<EOF
{"app_id": "${app_id}", "app_key": "${app_key}"}
EOF
)"
  run secretsmanager put-secret-value --secret-id "${ENV_PREFIX}/reed" \
    --secret-string "$(json reed.json <<EOF
{"api_key": "${reed_key}"}
EOF
)"
}

cmd_run() { # [source]
  local payload='{}'
  if [ -n "${1:-}" ]; then payload="{\"sources\":[\"$1\"]}"; fi
  run lambda invoke --function-name "${ENV_PREFIX}-ingest" --payload "$payload" \
    --cli-binary-format raw-in-base64-out "$WORK/out.json"
  [ "$DRY_RUN" = 1 ] || cat "$WORK/out.json"
  echo
  echo "Logs: aws logs tail /aws/lambda/${ENV_PREFIX}-ingest --since 10m" >&2
}

cmd_schedule() { # on|off
  local acct state
  acct=$(account_id)
  case "${1:-}" in
    on) state=ENABLED ;;
    off) state=DISABLED ;;
    *) echo "usage: $0 schedule on|off" >&2; exit 2 ;;
  esac
  # update-schedule replaces the whole definition, so every setting is sent again.
  schedule_args "$acct" "$state"
  run scheduler update-schedule "${SCHEDULE_ARGS[@]}"
}

cmd_status() {
  local acct
  acct=$(account_id)
  run scheduler get-schedule --name "${ENV_PREFIX}-ingest" \
    --query '{State:State,Expression:ScheduleExpression,Zone:ScheduleExpressionTimezone}'
  run s3 ls "s3://${ENV_PREFIX}-raw-${acct}/raw/" --recursive
}

# --- teardown ----------------------------------------------------------------------------------

cmd_teardown() {
  local acct key b
  acct=$(account_id)
  echo "Deleting everything 'deploy' created under prefix ${ENV_PREFIX} (including the data)." >&2
  if [ "$DRY_RUN" != 1 ]; then
    read -r -p "Type the prefix to confirm: " confirm
    [ "$confirm" = "$ENV_PREFIX" ] || { echo "cancelled" >&2; exit 1; }
  fi
  run scheduler delete-schedule --name "${ENV_PREFIX}-ingest"
  run cloudwatch delete-alarms --alarm-names "${ENV_PREFIX}-ingest-dlq-not-empty"
  run lambda delete-function --function-name "${ENV_PREFIX}-ingest"
  run logs delete-log-group --log-group-name "/aws/lambda/${ENV_PREFIX}-ingest"
  run iam delete-role-policy --role-name "${ENV_PREFIX}-ingest-scheduler" --policy-name invoke-ingest
  run iam delete-role --role-name "${ENV_PREFIX}-ingest-scheduler"
  run iam delete-role-policy --role-name "${ENV_PREFIX}-ingest-lambda" --policy-name ingest
  run iam delete-role --role-name "${ENV_PREFIX}-ingest-lambda"
  run sqs delete-queue \
    --queue-url "https://sqs.${REGION}.amazonaws.com/${acct}/${ENV_PREFIX}-ingest-dlq"
  run secretsmanager delete-secret --secret-id "${ENV_PREFIX}/adzuna" --force-delete-without-recovery
  run secretsmanager delete-secret --secret-id "${ENV_PREFIX}/reed" --force-delete-without-recovery
  for key in raw curated artifacts; do
    b="${ENV_PREFIX}-${key}-${acct}"
    empty_bucket "$b"
    run s3api delete-bucket --bucket "$b"
  done
}

cmd_teardown_bootstrap() {
  local acct b
  acct=$(account_id)
  b="${PREFIX}-tfstate-${acct}"
  echo "Deleting the ${PREFIX} state bucket and GitHub roles. The shared OIDC provider is kept." >&2
  if [ "$DRY_RUN" != 1 ]; then
    read -r -p "Type the prefix to confirm: " confirm
    [ "$confirm" = "$PREFIX" ] || { echo "cancelled" >&2; exit 1; }
  fi
  run iam detach-role-policy --role-name "${PREFIX}-github-plan" \
    --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess
  run iam delete-role-policy --role-name "${PREFIX}-github-plan" --policy-name terraform-state
  run iam delete-role --role-name "${PREFIX}-github-plan"
  run iam detach-role-policy --role-name "${PREFIX}-github-apply" \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
  run iam delete-role --role-name "${PREFIX}-github-apply"
  empty_bucket "$b"
  run s3api delete-bucket --bucket "$b"
}

# --- entry point -------------------------------------------------------------------------------

case "${1:-}" in
  bootstrap) cmd_bootstrap ;;
  deploy) cmd_deploy ;;
  secrets) cmd_secrets ;;
  run) cmd_run "${2:-}" ;;
  schedule) cmd_schedule "${2:-}" ;;
  status) cmd_status ;;
  teardown) cmd_teardown ;;
  teardown-bootstrap) cmd_teardown_bootstrap ;;
  *)
    sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//' >&2
    exit 2
    ;;
esac
