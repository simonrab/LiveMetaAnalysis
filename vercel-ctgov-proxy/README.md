# CT.gov clean-egress proxy (Vercel)

A tiny FastAPI passthrough that forwards `/api/v2/*` to
`clinicaltrials.gov/api/v2/*`. The LiveMeta backend calls this instead of CT.gov
directly, because CT.gov's Akamai WAF 403s the backend's Railway egress IP.
Vercel's network is not blocked, so requests succeed.

**Live deployment:** Vercel project `live-meta-analysis` →
`https://live-meta-analysis.vercel.app`. The backend is wired to it via the env
var `CTGOV_API_BASE=https://live-meta-analysis.vercel.app/api/v2` (set on the
Railway `livemeta-backend` service).

## Redeploy

```bash
cd vercel-ctgov-proxy
vercel --prod        # project: live-meta-analysis
```

## Verify egress reaches CT.gov

```bash
curl "https://live-meta-analysis.vercel.app/api/v2/studies?query.term=NCT01147250&fields=protocolSection&pageSize=1"
# -> JSON with a "studies" array = clean egress. A 403 = Vercel blocked too.
```

## Gotchas

- Vercel auto-detects this project as `fastapi`; the entrypoint must be a FastAPI
  app (`main.py`), not a Node function.
- **Deployment Protection must stay OFF** for this project, or the backend is
  redirected (302) to Vercel SSO and every fetch fails.
