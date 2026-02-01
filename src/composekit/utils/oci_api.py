import httpx


async def list_tags(
    client: httpx.AsyncClient,
    registry_host: str | None,
    repo: str,
    username: str | None = None,
    password: str | None = None,
) -> list[str]:
    if not registry_host or registry_host == "docker.io":
        registry_host = "index.docker.io"

    base = f"https://{registry_host}"
    url = f"{base}/v2/{repo}/tags/list"

    auth = (
        (username, password)
        if username is not None and password is not None
        else None
    )

    r = await client.get(url, auth=auth)
    if r.status_code == 200:
        return r.json().get("tags", []) or []

    if r.status_code == 401:
        www = r.headers.get("WWW-Authenticate", "")
        if www.lower().startswith("bearer"):
            parts = www[len("Bearer ") :].strip()
            params = {}
            for p in parts.split(","):
                if "=" not in p:
                    continue

                k, v = p.split("=", 1)
                params[k.strip()] = v.strip().strip('"')

            realm = params.pop("realm", None)
            if not realm:
                return []

            request = await client.get(realm, params=params, auth=auth)
            request.raise_for_status()
            token_json = request.json()
            token = token_json.get("token") or token_json.get("access_token")
            if not token:
                raise RuntimeError("Token endpoint returned no token")

            headers = {"Authorization": f"Bearer {token}"}
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            return r.json().get("tags", []) or []

    r.raise_for_status()
    return []
