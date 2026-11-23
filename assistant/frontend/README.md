Frontend Docker image for the AI Voice Assistant

Usage

Build and run locally:

```bash
# from the repo root
docker-compose build frontend
docker-compose up -d frontend
```

Set the API URL to point to your tunneled backend (eg. ngrok, Cloudflare Tunnel):

```bash
# example with ngrok public URL
# edit docker-compose.yml or run with environment override
docker-compose run -e FRONTEND_API_URL=https://abcd-1234.ngrok.io frontend
```

Notes

- The container writes `/config.js` at startup with `window.FRONTEND_API_URL` set.
- The app uses `window.API_BASE_URL` or the legacy `window.FRONTEND_API_URL` if set.
- Otherwise, when served from Floci on port `4566`, conversation API calls go to `http://127.0.0.1:8001`; on other origins they use `window.location.origin`.
- When served from Floci, TTS uses the native Windows FastAPI server at `http://127.0.0.1:8000` to retain its Windows SAPI voice. Keep that server running and allow the Floci origin in `CORS_ORIGINS`. Override this with `window.TTS_API_BASE_URL` in `config.js` if needed. On other origins, TTS uses the conversation API URL.

## Floci S3 frontend

The frontend and FastAPI stack can be deployed to Floci using Terraform. From the repository root, run:

```powershell
.\deploy_floci.ps1
```

The deployment script securely prompts for a PostgreSQL password (at least 12 characters) and a JWT secret (at least 32 characters). It re-prompts for short entries; reuse the same values on later deployments. It creates the Floci ECR repository, builds and pushes the backend image through Floci's local Docker registry at `localhost:5100`, provisions ElastiCache, resolves its Docker bridge address (Floci reports `localhost`, which is not usable from the task container), and applies the full Terraform stack. It then starts a localhost-only proxy on port 8001 because Floci does not publish Fargate task ports to Windows. Terraform creates the `speech-frontend` bucket and website, PostgreSQL, Redis, networking, ECS, and logging resources. Its state contains secrets, so keep `terraform.tfstate` private; Terraform state and `.tfvars` files are ignored by Git.

Terraform outputs the frontend URL, backend proxy URL, RDS endpoint, ElastiCache endpoint, ECR repository URL, and local Docker push URL. The Floci-hosted UI uses the ECS proxy at `http://127.0.0.1:8001` for conversation requests and the native server at `http://127.0.0.1:8000` for Windows SAPI TTS. Ollama remains native on Windows at `http://localhost:11434`; set Ollama to listen on an interface reachable from Docker, because the task uses `http://host.docker.internal:11434`.

The default model remains `llama3.2` (3.2B). To use the installed, larger 8B model for potentially higher-quality but slower responses, set `$env:TF_VAR_ollama_model = "llama3:latest"` before running `.\deploy_floci.ps1`.
