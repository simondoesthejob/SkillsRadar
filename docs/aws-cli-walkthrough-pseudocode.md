# AWS CLI walkthrough: pseudocode

A plain-language outline of `scripts/aws_cli_walkthrough.sh`. Each step is one AWS CLI call. The
Terraform resource it matches is in brackets.

## Settings

```
region   = eu-west-2
prefix   = "skillsradar-cli"          # differs from Terraform's names, so nothing clashes
env      = prefix + "-dev"
dry_run  = on or off                  # on: print each command, call nothing
```

## Helpers

```
run(command):
    print the command
    if dry_run is off:
        execute it

retry(command):
    try run(command), up to 8 times, waiting 10 seconds between tries
    # new IAM roles take a few seconds to become usable

secure_bucket(bucket):                # used for every bucket
    block all public access
    turn on versioning
    turn on encryption (AES256)

empty_bucket(bucket):                 # needed before deleting a versioned bucket
    repeat:
        list up to 1000 object versions and delete markers
        if none: stop
        delete them
```

## Step 1: `bootstrap` (state bucket and GitHub access)

```
account = ask AWS who I am

# The Terraform state bucket                         [aws_s3_bucket.state + 3 settings]
create bucket  "<prefix>-tfstate-<account>"
secure_bucket(that bucket)

# Let GitHub sign in without stored keys             [aws_iam_openid_connect_provider]
if GitHub's identity provider already exists in the account:
    reuse it                                         # only one is allowed per account
else:
    create it

# Role for pull requests (read-only)                 [aws_iam_role.plan]
create role "<prefix>-github-plan"
    trusted only by GitHub tokens whose subject is "repo:<repo>:pull_request"
attach the AWS-managed ReadOnlyAccess policy
add a small policy: may read and write the state bucket

# Role for deployments                               [aws_iam_role.apply]
create role "<prefix>-github-apply"
    trusted only by GitHub tokens whose subject is "repo:<repo>:environment:dev"
attach the AWS-managed AdministratorAccess policy    # to be tightened later
```

## Step 2: `deploy` (the working system)

```
account = ask AWS who I am

# Three data buckets                                 [modules/data]
for each of raw, curated, artifacts:
    create bucket "<env>-<name>-<account>"
    secure_bucket(it)
    add a housekeeping rule: abort unfinished uploads after 7 days,
                             delete old file versions after 30 days

# Empty containers for the API keys                  [aws_secretsmanager_secret x2]
create secret "<env>/adzuna"       # values are stored later
create secret "<env>/reed"

# Where failed runs go                               [aws_sqs_queue, aws_cloudwatch_log_group]
create queue "<env>-ingest-dlq"    # keeps messages 14 days, encrypted
create log group for the Lambda, keep logs 30 days

# What the Lambda is allowed to do                   [aws_iam_role.lambda + policy]
create role "<env>-ingest-lambda"   # trusted by the Lambda service
give it permission to:
    write files under raw/ in the raw bucket
    read the two secrets
    send messages to the failure queue
    write to its own log group

# The function itself                                [aws_lambda_function]
zip up the src/ folder
retry until the new role works:
    create Lambda "<env>-ingest"
        python 3.12, 256 MB, 3-minute timeout, handler skillsradar.handler.lambda_handler
        failure queue = the queue above
        settings: raw bucket name, secret ARNs, search queries

# The daily trigger                                  [aws_iam_role.scheduler, aws_scheduler_schedule]
create role "<env>-ingest-scheduler"   # trusted by EventBridge Scheduler
give it permission to: invoke the Lambda, send to the failure queue
retry until the new role works:
    create schedule "<env>-ingest"
        06:00 every day, London time
        starts DISABLED
        target = the Lambda, retry twice, send failures to the queue

# The alarm                                          [aws_cloudwatch_metric_alarm]
create alarm: fire when the failure queue has any message in it
```

## Step 3: `secrets` (store the API keys)

```
ask for the Adzuna app_id, Adzuna app_key and Reed api_key
    # typed at a prompt, so they never appear on a command line or in shell history
write each key to a temporary file inside a private folder
put the Adzuna values into secret "<env>/adzuna"
put the Reed value   into secret "<env>/reed"
the temporary folder is deleted when the script exits
```

## Step 4: `run [source]` (call the Lambda once)

```
if a source name was given:
    payload = only that source
else:
    payload = all sources
call the Lambda "<env>-ingest" with that payload
print what it returned          # for example: how many postings were written
remind me where the logs are
```

## Step 5: `schedule on|off` and `status`

```
schedule on|off:
    # an update replaces the whole schedule, so every setting is sent again
    update schedule "<env>-ingest" with state ENABLED or DISABLED

status:
    show the schedule's state, timing and time zone
    list the files in the raw bucket
```

## Step 6: `teardown` (delete what `deploy` made)

```
ask me to type the prefix to confirm       # a safeguard, because this deletes data
delete: schedule, alarm, Lambda, log group
delete: scheduler role (policy first, then role)
delete: Lambda role (policy first, then role)
delete: failure queue
delete: both secrets immediately (no recovery period)
for each data bucket:
    empty_bucket(it)
    delete the bucket
```

## Step 7: `teardown-bootstrap`

```
ask me to type the prefix to confirm
for each GitHub role:
    detach its managed policy, delete its own policy, delete the role
empty_bucket(state bucket), then delete it
leave the GitHub identity provider alone    # other things may use it
```

## What Terraform does that this does not

| Terraform | This script |
|---|---|
| Keeps a state file of what exists | Has no memory of what it made |
| Shows a plan before changing anything | Runs each call as soon as it is reached |
| Skips what already exists | Fails with "already exists" on a re-run |
| Changes only what differs | Cannot update; you edit or delete by hand |
| Works out the order from references | The order is fixed in the script |
