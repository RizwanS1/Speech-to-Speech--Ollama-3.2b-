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
- The app uses `window.FRONTEND_API_URL` if present; otherwise `window.location.origin` as fallback.
