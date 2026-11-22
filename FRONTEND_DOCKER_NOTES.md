How to run the frontend Docker image and connect to your local backend

## Backend authentication and conversation history

Create the local environment file and replace the example JWT secret with a random value of at least 32 bytes:

```powershell
Copy-Item .env.example .env
```

Start the PostgreSQL and Redis containers and run the FastAPI backend from the repository root:

```powershell
docker compose up -d postgres redis
.\.venv\Scripts\python.exe -m pip install -r assistant\server\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn assistant.server.main:app --host 127.0.0.1 --port 8000
```

The example Compose configuration publishes PostgreSQL on port `15432` and Redis on `16379`; the `.env.example` URLs match those ports. The browser UI requires registration or login before recording. Its combined speech request requires a bearer token and stores the transcript and reply for the current conversation session. Existing standalone STT, chat, and TTS routes remain available.

The UI reports per-request Ollama token counts, estimated USD token cost, server/Ollama latency, browser API round-trip time, TTS time, and total turn time. Local Ollama defaults to zero token cost. To estimate provider pricing instead, set `PROMPT_COST_PER_MILLION_TOKENS_USD` and `COMPLETION_COST_PER_MILLION_TOKENS_USD` in `.env` to the applicable USD rates per one million tokens, then restart the backend. The estimate covers text-model tokens only, not hardware electricity, speech recognition, or text-to-speech costs.

1. Build and run the frontend (serves the static UI on port 8081):

```bash
docker-compose build frontend
docker-compose up -d frontend
```

The frontend container will be available at http://localhost:8081

2. Expose your local backend (FastAPI) to the internet using a tunnel (choose one):

- ngrok:
  ```bash
  ngrok http 8001
  ```
  copy the https URL it provides (eg. https://abcd-1234.ngrok.io)

- Cloudflare Tunnel (example):
  follow Cloudflare Tunnel docs to forward `https://your-host` to `http://localhost:8001`

3. Update the frontend to call the tunneled URL:

- Edit `docker-compose.yml` and set `FRONTEND_API_URL` to your tunnel URL, or pass it at runtime:

```bash
docker-compose down
FRONTEND_API_URL=https://abcd-1234.ngrok.io docker-compose up -d frontend
```

4. Open `http://localhost:8081` in your browser — the UI will call the tunneled backend.

If you prefer to serve the static UI locally (no Docker) while the container runs on 8081, from the static folder run:

```powershell
Push-Location assistant\server\static
python -m http.server 8080
# open http://localhost:8080
Pop-Location
```

Security notes

- Restrict the tunnel access or use an auth token if exposing a laptop with sensitive models.
- Use HTTPS tunnels (ngrok/Cloudflare provide TLS).

Vercel deployment (recommended for static UI)

- Vercel does not run arbitrary Docker containers. Instead deploy the static frontend files (the contents of `assistant/server/static/`) directly to Vercel as a Static Site.
- To deploy on Vercel:
  1. Create a new Vercel project and link your repo (or just the `assistant/server/static` folder).
  2. Configure the build to be "No build" (it's already static) or set output directory to the static folder.
  3. After deployment you'll get a Vercel URL like `https://your-site.vercel.app`.
  4. The frontend must know the backend tunnel URL at runtime. Vercel provides environment variables, but since this is a static build you should inject the tunnel URL into a small `config.js` during your deployment pipeline or use Vercel Serverless Function to return the runtime config.

Cloudflare Tunnel (recommended for exposing your local backend)

- Install Cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation
- Create a tunnel and route a public hostname to your local backend on `http://localhost:8001`:

  ```powershell
  # authenticate (one-time)
  cloudflared login

  # create and run a tunnel bound to a hostname you control
  cloudflared tunnel create my-tts-tunnel
  cloudflared tunnel route dns my-tts-tunnel tunnel.example.com
  cloudflared tunnel run my-tts-tunnel --url http://localhost:8001
  ```

- The public hostname (e.g., `https://tunnel.example.com`) is the URL you should configure as your frontend API endpoint.

Vosk model installation notes

- I added a convenience script `install_vosk_model.ps1` at the repo root which downloads and extracts `vosk-model-small-en-us-0.15` into `./models`.
- Run it from PowerShell (may take several minutes and several GB of disk):

  ```powershell
  .\install_vosk_model.ps1
  # then set the env var for your server process
  $env:VOSK_MODEL_PATH = "$PWD\models\vosk-model-small-en-us-0.15"
  ```

- After installing, restart the FastAPI backend so it can load `vosk.Model($env:VOSK_MODEL_PATH)`.

Notes and caveats

- CORS: the frontend origin (Vercel or your Docker host) must be allowed by your FastAPI backend (configure `CORSMiddleware`).
- HTTPS: Cloudflare Tunnel gives you TLS; ensure `window.FRONTEND_API_URL` uses `https://`.
- Latency: this architecture keeps the heavy model local (good). The frontend on Vercel will call the public tunnel which forwards to your laptop; network latency is added but inference runs locally.
- Vercel static + Cloudflare Tunnel is a robust pattern for keeping models local while serving the UI globally.
