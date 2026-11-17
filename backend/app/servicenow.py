import httpx

from . import config


def _client() -> httpx.AsyncClient:
    if not (config.SN_INSTANCE and config.SN_USER and config.SN_PASSWORD):
        raise RuntimeError("ServiceNow credentials missing in .env")
    return httpx.AsyncClient(
        base_url=config.SN_INSTANCE,
        auth=(config.SN_USER, config.SN_PASSWORD),
        headers={"Accept": "application/json"},
        timeout=30,
    )


def is_mock() -> bool:
    return config.SN_MODE != "live"


async def check() -> dict:
    """Connectivity test: read one incident."""
    if is_mock():
        return {"ok": True, "mode": "mock"}
    try:
        async with _client() as c:
            r = await c.get("/api/now/table/incident", params={"sysparm_limit": 1})
        if r.status_code == 401:
            return {"ok": False, "error": "401 unauthorized: check SN_USER/SN_PASSWORD"}
        r.raise_for_status()
        return {"ok": True, "mode": "live", "instance": config.SN_INSTANCE}
    except Exception as e:
        return {"ok": False, "error": str(e)}
