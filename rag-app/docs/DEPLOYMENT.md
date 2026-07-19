# Deployment

Adaptive RAG is split into a backend API and a static frontend.

For automated CI/CD from `main`, see
[GitHub Actions Deployment](./GITHUB_ACTIONS.md).

## Backend

Install dependencies:

```bash
cd rag-app/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set environment variables:

```env
ANTHROPIC_API_KEY=your_key_here
PINECONE_API_KEY=your_pinecone_key_here
PINECONE_INDEX_NAME=document-rag-assistant
PINECONE_NAMESPACE=adaptive-rag
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
APP_BASIC_AUTH_USERNAME=admin
APP_BASIC_AUTH_PASSWORD=use-a-long-random-password
CORS_ORIGINS=https://rag.vinodmaneti.com
MAX_UPLOAD_MB=25
MAX_CACHED_CONTEXT_CHARS=120000
```

Run with a production ASGI server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

For a managed deployment, put this behind the platform's process manager or a reverse proxy. Pinecone persists vectors independently of the backend instance, so no vector-data volume is required.

The frontend polls `GET /operations/{operation_id}` while uploads and questions
run. Disable CDN caching for `/operations/*` and forward the `Authorization`
header so each response reflects current backend progress.

Use HTTPS in front of the backend. HTTP Basic credentials must not be sent over plain HTTP on a public network.

The app currently keeps one active document in `PINECONE_NAMESPACE`. Use a separate namespace per user, tenant, or document collection before supporting multiple users. Add S3 for original files and PostgreSQL for users, metadata, and chat history when those records must persist.

For Elastic Beanstalk, add every backend variable above under Environment
properties. Keep `PIP_NO_CACHE_DIR=true` to reduce installation disk usage.

## Frontend

Set the API base URL:

```env
VITE_API_BASE_URL=https://d27o32245p2wf.cloudfront.net
VITE_INACTIVITY_TIMEOUT_MS=180000
```

Build:

```bash
cd rag-app/frontend
npm install
npm run build
```

Deploy the current build to the S3 origin bucket:

```bash
aws s3 sync dist/ s3://rag-assistant-vinod \
  --delete \
  --exclude "index.html" \
  --cache-control "public,max-age=31536000,immutable"
aws s3 cp dist/index.html s3://rag-assistant-vinod/index.html \
  --cache-control "no-cache,no-store,must-revalidate" \
  --content-type "text/html"
aws cloudfront create-invalidation \
  --distribution-id EO2S42NNE2S8X \
  --paths "/*"
```

Current frontend URL:

```text
https://rag.vinodmaneti.com
```

Users will be prompted to sign in with the backend Basic Auth username and password.
After three minutes of inactivity, the frontend removes the stored credentials
and returns the user to the sign-in screen.

The frontend CloudFront distribution terminates HTTPS with an ACM certificate
for `rag.vinodmaneti.com` and reads the S3 bucket through Origin Access
Control. Route 53 maps the custom hostname to CloudFront. The S3 bucket is the
deployment destination, not the public application URL.

## Local Proxy

During development, Vite proxies `/api/*` to `http://localhost:8000`. In
production, `VITE_API_BASE_URL` points to the HTTPS backend CloudFront
distribution.

## Current AWS Request Flow

```text
Browser
  -> https://rag.vinodmaneti.com
  -> frontend CloudFront (EO2S42NNE2S8X)
  -> private S3 origin
  -> React calls https://d27o32245p2wf.cloudfront.net
  -> backend CloudFront (EO506AR7PQ60S)
  -> Nginx on EC2
  -> Uvicorn/FastAPI on port 8000
  -> Pinecone and Anthropic
```

The backend CloudFront behavior uses `Managed-CachingDisabled` and
`Managed-AllViewer`, allowing protected API requests and their `Authorization`
headers to reach FastAPI without caching API responses.
