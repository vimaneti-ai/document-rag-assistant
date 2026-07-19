# GitHub Actions Deployment

The repository includes `.github/workflows/deploy.yml`.

The workflow:

1. Compiles and tests the FastAPI backend.
2. Installs and builds the React frontend with `npm ci`.
3. On successful pushes to `main`, deploys the exact commit to EC2 through AWS
   Systems Manager.
4. Installs changed Python dependencies, restarts PM2, and checks `/health`.
5. Builds the production frontend, synchronizes it to S3, and optionally
   invalidates a frontend CloudFront distribution.

Pull requests only run validation. Production deployment requires the `main`
branch and the GitHub `production` environment.

## Relationship To `portfolio-app`

This pipeline follows the same release shape as
`vimaneti-ai/portfolio-app/.github/workflows/deploy.yml`:

1. Tests must pass before deployment.
2. The backend deploys to EC2 and restarts its process manager.
3. The frontend is built and synchronized to S3.
4. CloudFront is invalidated after a frontend release.

The authentication and transport are deliberately stronger here:

- `portfolio-app` stores an EC2 SSH key in GitHub and uses `scp`/`ssh`.
  This application uses SSM Run Command, so GitHub does not need an SSH key and
  EC2 port 22 does not need to accept GitHub runner addresses.
- `portfolio-app` uses long-lived AWS access-key secrets. This application uses
  GitHub OIDC and temporary role credentials.
- The frontend waits for a healthy backend deployment before publishing. This
  avoids releasing a UI that expects an API version that failed to deploy.
- The backend automatically restores the previous Git SHA when its health
  check fails.

## Why OIDC

GitHub authenticates to AWS with OpenID Connect. Do not create
`AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` repository secrets.

OIDC issues temporary credentials for each run. The AWS role trust policy
limits access to this repository's `production` environment.

## 1. Prepare EC2

The EC2 instance must:

- Be registered as an AWS Systems Manager managed node.
- Have SSM Agent running.
- Have an instance profile containing `AmazonSSMManagedInstanceCore`.
- Have Git, Python 3.11, PM2, and curl installed.
- Contain a clone of this repository.
- Contain the production `rag-app/backend/.env` file.

On EC2, find the application directory and PM2 process name:

```bash
pwd
git remote -v
pm2 list
```

The deployment keeps ignored files such as `.env` and `.venv`. It checks out
the exact Git commit without deleting those files.

Confirm that Systems Manager sees the instance:

```bash
aws ssm describe-instance-information \
  --region us-east-2 \
  --query 'InstanceInformationList[].InstanceId'
```

## 2. Add The GitHub OIDC Provider

In AWS IAM, add an OpenID Connect identity provider:

```text
Provider URL: https://token.actions.githubusercontent.com
Audience: sts.amazonaws.com
```

Create an IAM role named `document-rag-github-deploy`. Replace
`AWS_ACCOUNT_ID` in this trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:vimaneti-ai/document-rag-assistant:environment:production"
        }
      }
    }
  ]
}
```

## 3. Add Deployment Permissions

Attach a policy to `document-rag-github-deploy`. Replace the account, instance,
bucket, and optional CloudFront values:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListFrontendBucket",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::rag-assistant-vinod"
    },
    {
      "Sid": "WriteFrontendObjects",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::rag-assistant-vinod/*"
    },
    {
      "Sid": "SendBackendDeployment",
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ec2:us-east-2:AWS_ACCOUNT_ID:instance/EC2_INSTANCE_ID",
        "arn:aws:ssm:us-east-2::document/AWS-RunShellScript"
      ]
    },
    {
      "Sid": "ReadDeploymentResult",
      "Effect": "Allow",
      "Action": [
        "ssm:GetCommandInvocation",
        "ssm:ListCommandInvocations"
      ],
      "Resource": "*"
    },
    {
      "Sid": "InvalidateFrontend",
      "Effect": "Allow",
      "Action": "cloudfront:CreateInvalidation",
      "Resource": "arn:aws:cloudfront::AWS_ACCOUNT_ID:distribution/FRONTEND_DISTRIBUTION_ID"
    }
  ]
}
```

Remove `InvalidateFrontend` when the frontend does not use CloudFront.

Systems Manager Run Command can execute privileged commands. Keep
`ssm:SendCommand` restricted to this instance and `AWS-RunShellScript`.

## 4. Configure GitHub

Open:

```text
Repository -> Settings -> Environments -> New environment -> production
```

Add these environment variables:

| Variable | Example |
| --- | --- |
| `AWS_ROLE_ARN` | `arn:aws:iam::AWS_ACCOUNT_ID:role/document-rag-github-deploy` |
| `AWS_REGION` | `us-east-2` |
| `EC2_INSTANCE_ID` | `i-0123456789abcdef0` |
| `EC2_APP_DIR` | `/home/ubuntu/document-rag-assistant` |
| `EC2_DEPLOY_USER` | `ubuntu` |
| `PM2_APP_NAME` | Name shown by `pm2 list` |
| `FRONTEND_S3_BUCKET` | `rag-assistant-vinod` |
| `VITE_API_BASE_URL` | `https://d27o32245p2wf.cloudfront.net` |
| `VITE_INACTIVITY_TIMEOUT_MS` | `180000` |
| `FRONTEND_PUBLIC_URL` | `https://rag.vinodmaneti.com` |
| `FRONTEND_CLOUDFRONT_DISTRIBUTION_ID` | `EO2S42NNE2S8X` |

These are identifiers and build configuration, not API secrets. Keep Anthropic,
Pinecone, and Basic Auth values in the EC2 `.env` or AWS Secrets Manager.

For additional safety, enable required reviewers on the `production`
environment. The workflow will wait for approval before deployment can use the
AWS role.

The current frontend CloudFront distribution uses the ACM certificate for
`rag.vinodmaneti.com`, a Route 53 alias, and the private
`rag-assistant-vinod` S3 origin. Its deployment role must include
`cloudfront:CreateInvalidation` for distribution `EO2S42NNE2S8X`; otherwise
the application upload succeeds but the workflow fails at cache invalidation.

## 5. First Deployment

Commit and push:

```bash
git add .github README.md rag-app
git commit -m "ci: automate AWS deployment with GitHub Actions"
git push origin main
```

Open the repository's **Actions** tab and select **Test and Deploy**.

The workflow can also be started manually with **Run workflow**, but production
deployment is still limited to `main`.

## Deployment And Rollback

The backend deployment:

1. Records the currently deployed Git SHA.
2. Fetches the repository on EC2.
3. Checks out the workflow's exact SHA.
4. Installs requirements and compiles the backend. Existing deployments using
   `backend/venv` retain that environment; new deployments use
   `backend/.venv`.
5. Restarts or creates the configured PM2 process.
6. Calls `http://127.0.0.1:8000/health`.
7. Restores the previous SHA and any pre-deployment tracked EC2 patch, then
   restarts PM2 if the health check fails.

GitHub waits up to 30 minutes for the SSM command so initial Torch and
sentence-transformers installation is not mistaken for a failed deployment.

The frontend deploys only after the backend succeeds. Hashed assets receive a
one-year immutable cache header. `index.html` receives `no-cache`.

## Limitations

- The EC2 deployment assumes the repository is already cloned.
- A private repository requires an EC2 deploy key or another authenticated
  source-delivery method.
- Installing Torch or sentence-transformers on production can be slow.
- Rollback cannot reverse external Pinecone data changes.
- S3 deployment is not atomic, although hashed assets reduce mixed-version
  risk.
- The single EC2 instance remains a single point of failure.
