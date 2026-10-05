// Detect the environment: when running locally, call the API on port 8000 of the same host
// (localhost and 127.0.0.1 are different sites, so mixing them would drop the login cookie);
// otherwise (real domain, behind the reverse proxy) call the /api subpath on the same domain.
// If your real domain differs from "yourdomain.com" in the Caddyfile, update the line below to match.
const IS_LOCAL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
const API_BASE_URL = IS_LOCAL
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : `${window.location.origin}/api`;

// OAuth client ID from Google Cloud Console (APIs & Services > Credentials). Not a secret.
// Must be the same value as GOOGLE_CLIENT_ID in the backend .env.
const GOOGLE_CLIENT_ID = "";
