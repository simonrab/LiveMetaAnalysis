# CT.gov clean-egress proxy (deployed on Vercel as project `live-meta-analysis`).
#
# ClinicalTrials.gov's Akamai WAF 403s the Railway backend's datacenter egress
# IP. This forwards /api/v2/* to clinicaltrials.gov/api/v2/* from Vercel's
# network, which CT.gov does not block. The backend points at it by setting
# CTGOV_API_BASE=https://live-meta-analysis.vercel.app/api/v2.
#
# Vercel auto-detects this project as `fastapi`, so the proxy is a FastAPI app
# (a Node function is ignored). Keep Deployment Protection OFF, or the backend
# is redirected (302) to Vercel SSO and every fetch fails.
import httpx
from fastapi import FastAPI, Request, Response

app = FastAPI()

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.api_route("/api/{path:path}", methods=["GET"])
async def proxy(path: str, request: Request) -> Response:
    target = f"https://clinicaltrials.gov/api/{path}"
    if request.url.query:
        target += f"?{request.url.query}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        upstream = await client.get(target, headers=_HEADERS)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
        headers={"access-control-allow-origin": "*"},
    )
