# Access: IAM groups and the deployment user

Two groups are defined in `terraform/modules/iam_groups` and created by the stack in
`terraform/iam`:

| Group | Purpose | Lifetime |
|---|---|---|
| `skillsradar-bootstrap` | Run `terraform/bootstrap` (state bucket, GitHub OIDC roles) and, optionally, `terraform/envs/dev` from a laptop | Temporary: remove members once CI deploys |
| `skillsradar-operator` | Store API keys, invoke the ingest function, read data, logs and the dead-letter queue, run Athena queries in the environment workgroups | Standing |

Both groups also get a `require-mfa` policy (set `require_mfa = false` to omit it).

## Order of operations

Terraform cannot create the groups using the groups' own permissions, so the sequence matters:

1. **Use an identity that can already manage IAM.** For a new account, sign in as root once, create
   an admin identity (IAM Identity Center is best; otherwise an IAM user with
   `AdministratorAccess` and MFA), then stop using root. Never create root access keys.
2. **Create the groups** (local state, once):
   ```bash
   cd terraform/iam
   terraform init
   terraform apply
   ```
3. **Create the deployment user** in the console or CLI, enable MFA on it, and add it to the groups:
   ```bash
   aws iam add-user-to-group --user-name <user> --group-name skillsradar-bootstrap
   aws iam add-user-to-group --user-name <user> --group-name skillsradar-operator
   ```
4. **Get an MFA-authenticated session** as that user (access keys alone are denied by the MFA
   policy):
   ```bash
   aws sts get-session-token \
     --serial-number arn:aws:iam::<account-id>:mfa/<user> --token-code <6-digit-code>
   export AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...  AWS_SESSION_TOKEN=...
   ```
   Sessions expire (12 hours by default), so repeat when you see `ExpiredToken`.
5. **Run the bootstrap** (`terraform/bootstrap`, see the README), then set the GitHub variables.
6. **Remove the user from the bootstrap group** once CI is deploying:
   ```bash
   aws iam remove-user-from-group --user-name <user> --group-name skillsradar-bootstrap
   ```
   The user keeps operator access for day-to-day work.

Group membership is deliberately not managed in Terraform. A membership resource manages a
group's full member list and could remove people you added by hand.

## What the bootstrap group is really allowed to do

Be clear-eyed about this one. The bootstrap creates a role for CI that has `AdministratorAccess`
attached, and it needs to create that role and set its trust policy. A member who can do that can
also change a role's trust policy to let themselves assume it. **In practice the bootstrap group is
admin-equivalent.** That is why it is temporary, MFA-protected and scoped to `skillsradar-*` names
(which keeps mistakes contained and the policy honest, but is not a security boundary against a
malicious member).

Ways to tighten it later:
- Replace `AdministratorAccess` on the CI apply role with a policy listing only the services in
  `envs/dev` (on the roadmap), then shrink `github_oidc_managed_policy_arns` to match.
- Add a permissions boundary to every role the project creates, and require it on `iam:CreateRole`.

## Operator group: what is excluded on purpose

No access to the Terraform state bucket (state can contain sensitive values), no `GetSecretValue`
(operators can set API keys but not read them back), and nothing outside the `<prefix>-<env>`
resources.

## Caveats

- **Untested against a live account.** The policies were written from the services the Terraform
  uses, without Terraform or AWS available to run them. Expect to add an action when you first see
  `AccessDenied`. Paste the error and the missing action is usually named in it.
- **Secrets Manager `CreateSecret`** may not honour resource-level scoping in every case. If it
  is denied, widen that one statement's resource to `*` and tighten it again later.
- **Managed policy size limit.** Each managed policy may hold 6,144 characters, so the bootstrap
  permissions are split into two policies. Adding many more services means adding a third.
- **No CI for this stack, by design.** The roles GitHub Actions assumes must not be able to change
  who has access.
- **Account hygiene:** set an AWS Budget alert, and do not put long-lived access keys into GitHub.
  The workflows use OIDC and need none.
