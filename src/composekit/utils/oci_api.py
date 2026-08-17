import httpx


async def _list_tags_with_bearer_auth(
    client: httpx.AsyncClient,
    url: str,
    www: str,
    auth: tuple[str, str] | None,
) -> list[str]:
    if not www.lower().startswith("bearer"):
        return []

    parts = www[len("Bearer ") :].strip()
    params = {}
    for p in parts.split(","):
        if "=" not in p:
            continue

        k, v = p.split("=", 1)
        params[k.strip()] = v.strip().strip('"')

    realm = params.pop("realm", None)
    if not isinstance(realm, str):
        return []

    request = await client.get(realm, params=params, auth=auth)
    _ = request.raise_for_status()
    token_json: dict[str, str] = request.json()
    token = token_json.get("token", token_json.get("access_token"))
    if not isinstance(token, str):
        raise RuntimeError("Token endpoint returned no token")

    r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    _ = r.raise_for_status()
    return r.json().get("tags", []) or []


async def list_tags(
    client: httpx.AsyncClient,
    registry_host: str | None,
    repo: str,
    username: str | None = None,
    password: str | None = None,
) -> list[str]:
    if registry_host in (None, "", "docker.io"):
        registry_host = "index.docker.io"

    base = (
        f"https://{registry_host}"
        if not registry_host.startswith(("http://", "https://"))
        else registry_host
    )
    url = f"{base}/v2/{repo}/tags/list"

    auth = (
        (username, password)
        if username is not None and password is not None
        else None
    )

    r = await client.get(url, auth=auth)
    if r.status_code == 200:
        return r.json().get("tags", []) or []
    elif r.status_code == 401:
        www = r.headers.get("WWW-Authenticate", "")
        return await _list_tags_with_bearer_auth(client, url, www, auth)

    _ = r.raise_for_status()
    return []
