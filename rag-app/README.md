# Adaptive RAG App

This directory contains the complete Adaptive RAG application:

- `backend/`: FastAPI API, document processing, embeddings, Pinecone, Claude client
- `frontend/`: React + TypeScript chat UI
- `docs/`: setup, API, deployment, and production notes

The UI includes a live execution trace for uploads and questions, using
backend-recorded stages and timings for parsing, embeddings, Pinecone,
prompt caching, Claude generation, and citations.

After an upload, the pipeline renders a branching document map with real chunk
ranges, overlap bands, embedding samples, and the Pinecone destination.

After each answer, the UI renders the real query vector preview, ranked
Pinecone scores and excerpts, prompt inputs, cache behavior, model token usage,
and final citation count directly beneath that answer.

Start here:

- [Setup](./docs/SETUP.md)
- [API](./docs/API.md)
- [Deployment](./docs/DEPLOYMENT.md)
- [GitHub Actions Deployment](./docs/GITHUB_ACTIONS.md)
- [CI/CD End-to-End Process](./docs/CI_CD_PROCESS.md)
- [Production Notes](./docs/PRODUCTION.md)
- [Project Overview](./docs/PROJECT_OVERVIEW.md)
