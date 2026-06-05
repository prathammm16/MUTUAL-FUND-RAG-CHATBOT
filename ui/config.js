// Local dev: empty string → same-origin requests via FastAPI.
// Vercel: overwritten at build time from VITE_API_BASE_URL (see package.json).
window.__API_BASE__ = "";
