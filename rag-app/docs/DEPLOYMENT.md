# Deployment

Adaptive RAG is split into a backend API and a static frontend.

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
CORS_ORIGINS=http://rag-assistant-vinod.s3-website.us-east-2.amazonaws.com
MAX_UPLOAD_MB=25
MAX_CACHED_CONTEXT_CHARS=120000
```

Run with a production ASGI server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

For a managed deployment, put this behind the platform's process manager or a reverse proxy. Pinecone persists vectors independently of the backend instance, so no vector-data volume is required.

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

Deploy the current build to the S3 website bucket:

```bash
aws s3 sync dist/ s3://rag-assistant-vinod --delete
```

Current frontend URL:

```text
http://rag-assistant-vinod.s3-website.us-east-2.amazonaws.com
```

Users will be prompted to sign in with the backend Basic Auth username and password.
After three minutes of inactivity, the frontend removes the stored credentials
and returns the user to the sign-in screen.

## Local Proxy

During development, Vite proxies `/api/*` to `http://localhost:8000`. In production, use `VITE_API_BASE_URL` or a reverse proxy that routes `/api` to the backend.

The S3 website endpoint supports HTTP only. Put CloudFront and an ACM
certificate in front of the frontend before treating the deployment as
production, then replace `CORS_ORIGINS` with the final HTTPS frontend origin.
