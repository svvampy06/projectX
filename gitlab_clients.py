import httpx
import os

GITLAB_API_URL = os.getenv(
    "GITLAB_API_URL",
    "https://gitlab.wildberries.ru/api/v4"
)
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "")
HEADERS = {"PRIVATE-TOKEN": GITLAB_TOKEN} if GITLAB_TOKEN else {}
PAGE_SIZE = 100
REQUEST_TIMEOUT = 60.0

class GitlabAPIError(Exception):
    """Общая ошибка при работе с GitLab API"""

class GroupNotFoundError(GitlabAPIError):
    """Группа не найдена (404)"""

async def fetch_group_hierarchy(group_path: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=HEADERS) as client:
        resp = await client.get(f"{GITLAB_API_URL}/groups/{group_path}")
        resp.raise_for_status()
        group = resp.json()
        groups: list[dict] = [{
            "name": group["path"],
            "full_path": group["full_path"],
            "id": group["id"],
            "url": group["web_url"],
        }]
        await _collect_subgroups(client, group["id"], groups)
        return groups

async def _collect_subgroups(client: httpx.AsyncClient, group_id: int, groups: list[dict]):
    page = 1
    seen_paths = {g["full_path"] for g in groups}
    while True:
        r = await client.get(
            f"{GITLAB_API_URL}/groups/{group_id}/subgroups",
            params={"per_page": PAGE_SIZE, "page": page},
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        for sg in batch:
            name = sg["path"]
            full = sg["full_path"]
            sg_id = sg["id"]
            url = sg["web_url"]
            if full not in seen_paths:
                groups.append({"name": name, "full_path": full, "id": sg_id, "url": url})
                seen_paths.add(full)
                await _collect_subgroups(client, sg_id, groups)
        next_page = r.headers.get("X-Next-Page")
        if not next_page or not next_page.isdigit():
            break
        page = int(next_page)

async def fetch_group_projects(group_path: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        url = f"{GITLAB_API_URL}/groups/{group_path}"
        try:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise GroupNotFoundError(f"Group '{group_path}' not found") from exc
            raise GitlabAPIError(
                f"GitLab API returned {exc.response.status_code} for {url}"
            ) from exc
        except httpx.RequestError as exc:
            raise GitlabAPIError(f"Network error while fetching group '{group_path}'") from exc
        group = resp.json()
        group_id = group["id"]
        repos: list[dict] = []
        await _collect_projects(client, group_id, repos)
        return repos

async def _get_all_pages(
    client: httpx.AsyncClient, url: str, params: dict
) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        try:
            r = await client.get(
                url,
                headers=HEADERS,
                params={**params, "per_page": PAGE_SIZE, "page": page},
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GitlabAPIError(
                f"GitLab API returned {exc.response.status_code} for {url}"
            ) from exc
        except httpx.RequestError as exc:
            raise GitlabAPIError(f"Network error while requesting {url}") from exc
        batch = r.json()
        if not batch:
            break
        items.extend(batch)
        next_page = r.headers.get("X-Next-Page")
        if not next_page:
            break
        page = int(next_page)
    return items

async def _collect_projects(
    client: httpx.AsyncClient, group_id: int, repos: list[dict]
):
    projects_url = f"{GITLAB_API_URL}/groups/{group_id}/projects"
    projects = await _get_all_pages(
        client, projects_url, {"include_subgroups": "false"}
    )
    for project in projects:
        if project.get("archived"):
            continue
        repos.append({
            "name": project["path"],
            "url": project["web_url"],
            "group_path": project["namespace"]["full_path"],
            "repo_id": project["id"],
        })
    subgroups_url = f"{GITLAB_API_URL}/groups/{group_id}/subgroups"
    subgroups = await _get_all_pages(client, subgroups_url, {})
    for subgroup in subgroups:
        await _collect_projects(client, subgroup["id"], repos)
