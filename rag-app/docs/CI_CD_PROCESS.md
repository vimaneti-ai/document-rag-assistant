# CI/CD Process: End-to-End Explanation

This document explains how CI/CD was introduced for Document RAG Assistant,
what every component does, which deployment problems were discovered, and how
the final release process works.

For the exact IAM policies and configuration values, see
[GITHUB_ACTIONS.md](./GITHUB_ACTIONS.md).

## 1. What CI/CD Means

**Continuous Integration (CI)** automatically validates every proposed code
change. In this project, CI:

1. Installs the backend dependencies.
2. Compiles the Python modules.
3. Runs the backend unit tests.
4. Installs the frontend dependencies.
5. Builds the React production bundle.

**Continuous Deployment (CD)** publishes validated changes automatically. In
this project, CD:

1. Deploys the backend to EC2.
2. Restarts FastAPI through PM2.
3. Verifies the backend health endpoint.
4. Publishes the React frontend to S3.

Pull requests run CI only. A successful push to `main` runs both CI and CD.

## 2. Final Architecture

```text
Developer
   |
   | git push origin main
   v
GitHub repository
   |
   v
GitHub Actions: Test and Deploy
   |
   +---- Backend tests
   |
   +---- Frontend build
   |
   +---- GitHub OIDC ----> AWS IAM deployment role
   |                            |
   |                            v
   |                     Systems Manager Run Command
   |                            |
   |                            v
   |                     EC2 Git checkout
   |                     Python dependencies
   |                     PM2 restart
   |                     FastAPI /health check
   |
   +---- Production React build
   |
   +---- S3 synchronization
```

The deployed application traffic follows a separate path:

```text
Browser
   |
   +---- S3 website --------> React frontend
   |
   +---- Backend CloudFront -> Nginx on EC2 -> Uvicorn -> FastAPI
                                                    |
                                                    +-> Pinecone
                                                    +-> Claude API
```

## 3. Responsibilities

| Component | Responsibility |
| --- | --- |
| GitHub repository | Source of truth for application code |
| GitHub Actions | Tests, builds, and coordinates releases |
| GitHub `production` environment | Stores non-secret deployment configuration |
| GitHub OIDC | Gives a workflow temporary AWS credentials |
| AWS IAM deployment role | Limits which AWS actions the workflow may perform |
| AWS Systems Manager | Runs deployment commands on EC2 without SSH keys |
| EC2 | Hosts the FastAPI backend |
| Git on EC2 | Checks out the exact commit being deployed |
| PM2 | Keeps Uvicorn running and restarts it during deployment |
| Uvicorn | Serves the FastAPI application |
| Nginx | Proxies HTTP traffic to Uvicorn |
| S3 | Hosts the compiled React frontend |
| CloudFront | Provides the public HTTPS endpoint for the backend |
| Pinecone | Stores document vectors and document state |
| Anthropic | Generates document-grounded answers |

## 4. Why PM2 Was Retained

PM2 was already running the backend reliably as `rag-backend`. It provides:

- Process restart after application failure.
- Startup persistence after an EC2 reboot when `pm2 startup` and `pm2 save`
  are configured.
- A consistent restart command for deployments.
- Application status and log commands.

`systemd` would also work, but replacing a stable process manager would have
added migration work without improving the user-facing application. The
workflow therefore integrates with the existing PM2 process.

## 5. EC2 Discovery And Preparation

Before automating deployment, the running server was inspected instead of
assuming its layout.

The inspection established:

```text
Deployment user: ubuntu
Repository root: /home/ubuntu/document-rag-assistant
Backend directory: /home/ubuntu/document-rag-assistant/rag-app/backend
PM2 process: rag-backend
Backend port: 8000
Nginx port: 80
```

PM2 showed that the application used `backend/venv`, while the original
deployment script expected `backend/.venv`. The script was updated to preserve
an existing `venv` and use `.venv` for a new installation.

Nginx was confirmed to proxy:

```text
port 80 -> http://127.0.0.1:8000
```

This confirmed that local health checks could use `127.0.0.1:8000`.

## 6. Protecting Existing EC2 Changes

The EC2 repository was four commits behind GitHub and contained manual,
uncommitted changes in `main.py` and `rag_engine.py`.

Deploying immediately with `git checkout --force` would have overwritten those
files. Before the first automated release:

1. A binary Git patch was saved under `~/deployment-backups/`.
2. Runtime state and manual backup files were copied into the backup.
3. The EC2 working files were compared with `origin/main`.
4. The current GitHub implementation was confirmed to supersede the older
   server implementation.

The deployment workflow also captures any tracked EC2 diff before checkout. If
deployment fails, it restores:

1. The previous Git commit.
2. The pre-deployment tracked patch.
3. The previous PM2 application.

Ignored files such as `.env` and virtual environments are not removed by the
deployment checkout.

## 7. Enabling AWS Systems Manager

GitHub needs a secure method to run commands on EC2. Systems Manager Run
Command was selected instead of SSH.

An EC2 IAM role named `document-rag-ec2-ssm` was created with:

```text
AmazonSSMManagedInstanceCore
```

The role was attached to the EC2 instance.

On Ubuntu, SSM Agent was already installed as a Snap package. Its service name
was:

```text
amazon-ssm-agent.amazon-ssm-agent
```

The standard `amazon-ssm-agent.service` name did not exist, which is expected
for the Ubuntu Snap installation. Fleet Manager then reported the EC2 instance
as `Online`.

SSM provides these advantages:

- GitHub does not store an EC2 SSH private key.
- Port 22 does not need to accept changing GitHub runner addresses.
- AWS records Run Command activity for auditing.
- IAM can restrict deployment to one instance and one command document.

## 8. Configuring GitHub OIDC

The AWS IAM OIDC provider uses:

```text
Provider URL: https://token.actions.githubusercontent.com
Audience: sts.amazonaws.com
```

The deployment role is:

```text
document-rag-github-deploy
```

Its trust policy permits only tokens matching:

```text
repo:vimaneti-ai/document-rag-assistant:environment:production
```

This means another repository, branch-only workflow, or GitHub environment
cannot assume the role.

OIDC was chosen instead of storing `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY` in GitHub. GitHub receives short-lived AWS credentials
for each deployment run.

## 9. Least-Privilege AWS Permissions

The deployment role has an inline policy that permits:

- Listing the frontend S3 bucket.
- Uploading and deleting frontend objects.
- Sending `AWS-RunShellScript` to the designated EC2 instance.
- Reading the resulting SSM command status.
- Optionally invalidating the frontend CloudFront distribution.

The role does not have `AdministratorAccess`, access to application API keys,
or general command access to every EC2 instance.

## 10. GitHub Production Environment

The repository contains a GitHub environment named `production`.

It stores non-secret identifiers and build configuration:

| Variable | Purpose |
| --- | --- |
| `AWS_ROLE_ARN` | IAM role assumed through OIDC |
| `AWS_REGION` | Region containing EC2 and SSM |
| `EC2_INSTANCE_ID` | Backend deployment target |
| `EC2_APP_DIR` | Repository root on EC2 |
| `EC2_DEPLOY_USER` | Linux user that owns Git and PM2 |
| `PM2_APP_NAME` | PM2 process restarted by deployment |
| `FRONTEND_S3_BUCKET` | S3 deployment destination |
| `VITE_API_BASE_URL` | Public HTTPS backend URL compiled into React |
| `VITE_INACTIVITY_TIMEOUT_MS` | Frontend automatic logout interval |
| `FRONTEND_PUBLIC_URL` | URL used for the frontend smoke test |
| `FRONTEND_CLOUDFRONT_DISTRIBUTION_ID` | Optional cache invalidation target |

Application secrets are not GitHub environment variables. They remain in the
ignored EC2 `rag-app/backend/.env` file or should be migrated to AWS Secrets
Manager.

## 11. Production Environment Validation

Before the first deployment, EC2 was checked for these values without printing
their contents:

```text
ANTHROPIC_API_KEY
PINECONE_API_KEY
PINECONE_INDEX_NAME
PINECONE_NAMESPACE
APP_BASIC_AUTH_USERNAME
APP_BASIC_AUTH_PASSWORD
CORS_ORIGINS
```

`PINECONE_NAMESPACE` was missing and was added as:

```text
PINECONE_NAMESPACE=adaptive-rag
```

The CORS configuration includes the deployed frontend origin. Pinecone creates
the namespace when the application first writes records; it does not need to
be created manually.

## 12. Workflow Triggers

The workflow is stored at:

```text
.github/workflows/deploy.yml
```

It runs for:

```yaml
pull_request:
push:
  branches:
    - main
workflow_dispatch:
```

The resulting behavior is:

| Event | Tests | Backend deployment | Frontend deployment |
| --- | --- | --- | --- |
| Pull request | Yes | No | No |
| Push to `main` | Yes | Yes | Yes |
| Manual run on `main` | Yes | Yes | Yes |

Creating the GitHub environment alone does not start CI/CD. GitHub starts the
workflow because `deploy.yml` is committed under `.github/workflows/` and its
trigger matches the Git event.

## 13. CI Jobs

### Backend Tests

The backend job:

1. Checks out the commit.
2. Configures Python 3.11.
3. Restores the pip dependency cache when possible.
4. Installs `requirements.txt`.
5. Compiles the main backend modules.
6. Runs unit tests.

The tests cover document chunk positions, pipeline progress state, Pinecone
build/retrieval/clear behavior, and missing API-key errors.

### Frontend Build

The frontend validation job:

1. Checks out the commit.
2. Configures Node.js.
3. Restores the npm cache when possible.
4. Runs `npm ci`.
5. Runs the TypeScript and Vite production build.

Backend tests and frontend validation can run independently. Deployment starts
only after both succeed.

## 14. Backend Deployment

GitHub requests temporary AWS credentials through OIDC and sends an SSM Run
Command to EC2.

The SSM command:

1. Confirms that `EC2_APP_DIR` contains a Git repository.
2. Records the current Git SHA.
3. Saves any tracked, uncommitted EC2 diff for rollback.
4. Fetches the latest repository objects.
5. Checks out the exact GitHub Actions commit SHA.
6. Copies the deployment script to a temporary location.
7. Runs the script as the non-root deployment user.

The deployment script:

1. Locates PM2, including installations managed by NVM.
2. Confirms the backend `.env` file exists.
3. Reuses `backend/venv` when already present.
4. Creates `backend/.venv` for a new installation.
5. Installs Python requirements.
6. Compiles the backend modules.
7. Restarts the existing PM2 application with updated environment variables.
8. Creates the PM2 process when it does not exist.
9. Saves the PM2 process list.
10. Polls `/health` for up to 60 seconds.

GitHub polls the SSM command for up to 30 minutes. This avoids treating the
large Torch and sentence-transformers installation as a failure after the
short default waiter period.

## 15. Rollback Behavior

When the backend health check fails:

1. The deployment script prints recent PM2 logs.
2. The SSM wrapper checks out the previous Git SHA.
3. It reapplies the tracked EC2 patch captured before deployment.
4. It reruns the deployment script for the previous code.
5. The GitHub Actions job fails visibly.
6. The frontend deployment does not start.

Rollback cannot reverse changes made to external systems such as Pinecone.
Schema and data migrations therefore need their own backward-compatible
strategy.

## 16. Frontend Deployment

The frontend job starts only after successful backend deployment.

It:

1. Checks out the same commit.
2. Installs dependencies with `npm ci`.
3. Builds React with the production API URL and inactivity timeout.
4. Synchronizes `dist/` to S3.
5. Deletes S3 files that no longer exist in the build.
6. Assigns long-lived immutable caching to hashed assets.
7. Assigns `no-cache` to `index.html`.
8. Optionally invalidates CloudFront.
9. Optionally performs an HTTP smoke test against the frontend.

Hashed assets can be cached for one year because a content change generates a
new filename. `index.html` must not be cached long term because it identifies
the current asset filenames.

## 17. First Successful Deployment

The first automated release was triggered by commit:

```text
7865f3d ci: automate AWS deployment with GitHub Actions
```

The run completed successfully in approximately three minutes. Verification
confirmed:

- Local EC2 `/health` returned `{"status":"ok"}`.
- The backend CloudFront `/health` returned `{"status":"ok"}`.
- The S3 website returned HTTP 200.
- `index.html` had `no-cache,no-store,must-revalidate`.
- Its S3 modification time matched the GitHub Actions release.

## 18. Normal Development Process

For a feature branch:

```bash
git checkout -b feature/example
git add .
git commit -m "feat: describe the change"
git push -u origin feature/example
```

Open a pull request. CI validates it without deploying production.

After review, merge to `main`. The push to `main` automatically runs the full
test and deployment pipeline.

For a direct release:

```bash
git add <intended-files>
git diff --cached
git commit -m "type: concise description"
git push origin main
```

A deployment can also be started from:

```text
GitHub -> Actions -> Test and Deploy -> Run workflow
```

## 19. Operational Verification

Check the EC2 deployment:

```bash
cd /home/ubuntu/document-rag-assistant
git rev-parse --short HEAD
pm2 status
pm2 logs rag-backend --lines 50 --nostream
curl --fail http://127.0.0.1:8000/health
```

Check the public application:

```bash
curl --fail https://d27o32245p2wf.cloudfront.net/health
curl -I http://rag-assistant-vinod.s3-website.us-east-2.amazonaws.com
```

Then use the browser to test:

1. Sign in.
2. Upload a supported document.
3. Confirm the ingestion visualization.
4. Ask a document-grounded question.
5. Confirm answer sources, usage, and question visualization.
6. Ask a second question to exercise conversation history and prompt caching.
7. Clear the document.
8. Confirm automatic logout after inactivity.

## 20. Problems Found And Resolved

| Problem | Impact | Resolution |
| --- | --- | --- |
| `/home/ubuntu` was not a Git repository | Initial commands could not identify the deployment | Located the repository through PM2's process working directory |
| EC2 was four commits behind GitHub | A release would replace older server code | Backed up changes and confirmed GitHub was authoritative |
| EC2 contained uncommitted Python changes | Forced checkout could destroy the running version | Saved patches and added tracked-patch rollback |
| EC2 used `venv`; script expected `.venv` | Dependencies could install into the wrong environment | Added existing-`venv` detection |
| Ubuntu had no standard SSM service | It appeared that SSM Agent was missing | Identified the active Snap service |
| EC2 was initially unmanaged by SSM | GitHub could not issue deployment commands | Attached an SSM instance role and verified Fleet Manager `Online` |
| Default SSM waiter was too short | Torch installation could appear to fail | Added polling with a 30-minute deadline |
| `PINECONE_NAMESPACE` was missing | Production configuration was incomplete | Added `adaptive-rag` explicitly |
| Frontend and API URLs could be confused | React could send API calls to S3 | Separated `FRONTEND_PUBLIC_URL` and `VITE_API_BASE_URL` |
| Long-lived AWS keys were an option | Credential leakage and rotation risk | Used GitHub OIDC temporary credentials |
| Frontend could deploy after a failed backend | UI and API versions could diverge | Made frontend deployment depend on backend success |

## 21. Security Model

The pipeline protects credentials in several ways:

- AWS access keys are not stored in GitHub.
- OIDC credentials are short-lived.
- The IAM trust policy names one repository and environment.
- The IAM permissions target one EC2 instance and one S3 bucket.
- SSM replaces SSH-key deployment.
- Backend API keys and passwords remain outside Git.
- `.env`, virtual environments, frontend dependencies, and build output are
  ignored.
- Basic Auth protects application endpoints.
- `/health` remains public for infrastructure checks.

The current frontend S3 website uses HTTP. Before treating the application as
fully production-ready, serve the frontend through CloudFront HTTPS and update
`FRONTEND_PUBLIC_URL` and `CORS_ORIGINS`. An HTTP page that accepts credentials
can be modified in transit even when its API endpoint uses HTTPS.

## 22. Current Limitations

- A single EC2 instance is a single point of failure.
- PM2 restarts briefly interrupt the backend.
- Installing large Python dependencies during deployment can be slow.
- The S3 publication is not a fully atomic release.
- Rollback does not undo Pinecone data changes.
- Basic Auth is appropriate for a controlled demo, not multi-user identity.
- The application uses one Pinecone namespace and one active document.
- Original uploaded files and chat history are not stored durably.

Recommended next improvements:

1. Put the frontend behind CloudFront HTTPS.
2. Remove public EC2 port 8000 access after confirming CloudFront uses Nginx
   port 80.
3. Move backend secrets to AWS Secrets Manager or Parameter Store.
4. Add CloudWatch alarms and centralized logs.
5. Add an approval reviewer to the GitHub `production` environment.
6. Build a backend deployment artifact or container instead of installing all
   dependencies during every release.
7. Add per-user authentication and Pinecone namespaces before multi-user use.

## 23. Short Explanation For Reviewers

> The project uses GitHub Actions for continuous integration and deployment.
> Pull requests compile and test the FastAPI backend and build the React
> frontend. A successful push to `main` authenticates to AWS through GitHub
> OIDC, so no long-lived AWS keys are stored in GitHub. AWS Systems Manager
> checks out the exact commit on EC2, installs dependencies, restarts the
> Uvicorn process through PM2, and verifies `/health`. If the health check
> fails, it restores the previous commit and tracked server patch. Only after
> the backend is healthy does the workflow build React and synchronize it to
> S3 with appropriate cache headers. The result is a repeatable, auditable
> deployment with testing, least-privilege AWS access, health verification,
> and rollback protection.
