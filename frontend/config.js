// Detect the environment: when running locally, call localhost:8000 directly;
// otherwise (real domain, behind the reverse proxy) call the /api subpath on the same domain.
// If your real domain differs from "yourdomain.com" in the Caddyfile, update the line below to match.
const API_BASE_URL =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : `${window.location.origin}/api`;
