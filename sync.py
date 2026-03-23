from datetime import datetime
from sqlalchemy import select, delete, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models import groups, repositories
from gitlab_clients import fetch_group_projects, fetch_group_hierarchy
from db import database
from typing import Optional, List
from schemas import GroupsOut

async def sync_all_groups():
    q = select(groups.c.group_path)
    rows = await database.fetch_all(q)
    for row in rows:
        await sync_group(row["group_path"])
    return True

async def sync_group(group_path: str):
    all_groups = await fetch_group_hierarchy(group_path)
    now = datetime.utcnow()
    for gp in all_groups:
        group_name = gp["name"]
        group_path_val = gp["full_path"]
        group_id_val = gp["id"]
        url_val = gp["url"]
        parent = group_path_val.rsplit("/", 1)[0] if "/" in group_path_val else None
        stmt = (
            pg_insert(groups)
            .values(
                name=group_name,
                group_path=group_path_val,
                parent_group_path=parent,
                last_synced=now,
                group_id=group_id_val,
                url=url_val,
            )
            .on_conflict_do_update(
                index_elements=[groups.c.group_path],
                set_={
                    "name": group_name,
                    "last_synced": now,
                    "parent_group_path": parent,
                    "group_id": group_id_val,
                    "url": url_val,
                },
            )
        )
        await database.execute(stmt)

    repos = await fetch_group_projects(group_path)
    gitlab_urls = {r["url"] for r in repos}
    repo_paths = {r["group_path"] for r in repos}
    q = select(groups.c.group_path, groups.c.group_id).where(groups.c.group_path.in_(repo_paths))
    rows = await database.fetch_all(q)
    path2id = {r["group_path"]: r["group_id"] for r in rows}
    for r in repos:
        r["group_id"] = path2id[r["group_path"]]

    async with database.transaction():
        db_rows = await database.fetch_all(
            select(repositories.c.url).where(repositories.c.group_path == group_path)
        )
        db_urls = {r["url"] for r in db_rows}
        to_delete = db_urls - gitlab_urls
        if to_delete:
            await database.execute(
                delete(repositories).where(
                    repositories.c.group_path == group_path,
                    repositories.c.url.in_(to_delete),
                )
            )
        if repos:
            upsert_stmt = (
                pg_insert(repositories)
                .values(repos)
                .on_conflict_do_update(
                    index_elements=[repositories.c.url],
                    set_={
                        "repo_id":     pg_insert(repositories).excluded.repo_id,
                        "name":        pg_insert(repositories).excluded.name,
                        "group_path":  pg_insert(repositories).excluded.group_path,
                        "group_id":    pg_insert(repositories).excluded.group_id,
                    },
                )
                .returning(
                    repositories.c.repo_id,
                    repositories.c.id,
                    repositories.c.name,
                    repositories.c.url,
                    repositories.c.group_path,
                    repositories.c.group_id,
                )
            )
            rows = await database.fetch_all(upsert_stmt)
        else:
            rows = []
    return [
        {
            "repo_id":    r["repo_id"],
            "id":         r["id"],
            "name":       r["name"],
            "url":        r["url"],
            "group_path": r["group_path"],
            "group_id":   r["group_id"],
        }
        for r in rows
    ]

async def get_group_tree(group_path: str) -> dict:
    group_rows = await database.fetch_all(
        select(
            groups.c.name, 
            groups.c.id, 
            groups.c.group_path, 
            groups.c.parent_group_path, 
            groups.c.group_id, 
            groups.c.url
        )
    )
    group_map = {r["group_path"]: r for r in group_rows}

    if group_path not in group_map:
        await sync_group(group_path)
        group_rows = await database.fetch_all(
            select(
                groups.c.name,
                groups.c.id, 
                groups.c.group_path, 
                groups.c.parent_group_path, 
                groups.c.group_id, 
                groups.c.url
            )
        )
        group_map = {r["group_path"]: r for r in group_rows}
        if group_path not in group_map:
            return None

    def collect_paths(root_path):
        paths = [root_path]
        for g in group_map.values():
            if g["parent_group_path"] == root_path:
                paths.extend(collect_paths(g["group_path"]))
        return paths

    wanted_paths = collect_paths(group_path)

    repo_rows = await database.fetch_all(
        select(
            repositories.c.repo_id,
            repositories.c.name,
            repositories.c.url,
            repositories.c.group_path,
            repositories.c.group_id,
        ).where(repositories.c.group_path.in_(wanted_paths))
    )
    repos_by_group = {}
    for r in repo_rows:
        repos_by_group.setdefault(r["group_path"], []).append(r)

    def build_tree(path):
        group = group_map[path]
        node = {
            "id": group["group_id"],
            "group_path": path,
            "url": group["url"],
            "repositories": repos_by_group.get(path, []),
            "subgroups": [],
        }
        children = [
            g for g in group_map.values() if g["parent_group_path"] == path
        ]
        node["subgroups"] = [build_tree(child["group_path"]) for child in children]
        return node

    return build_tree(group_path)

async def find_repo(group_path: str, repo_name: str):
    return await database.fetch_one(
        select(
            repositories.c.repo_id,
            repositories.c.name,
            repositories.c.url,
            repositories.c.group_path,
            repositories.c.group_id,
        ).where(
            and_(
                repositories.c.group_path == group_path,
                repositories.c.name == repo_name,
            )
        )
    )

async def search_repositories(
    name: Optional[str] = None,
    repo_id: Optional[int] = None,
) -> List[dict]:
    conditions = []
    if name is not None:
        conditions.append(repositories.c.name == name)
    if repo_id is not None:
        conditions.append(repositories.c.repo_id == repo_id)
    if not conditions:
        return []

    stmt = select(
        repositories.c.repo_id,
        repositories.c.name,
        repositories.c.url,
        repositories.c.group_path,
        repositories.c.group_id,
    ).where(and_(*conditions))
    return await database.fetch_all(stmt)

async def get_groups_list() :
    gps = await database.fetch_all(
        select(
            groups.c.name,
            groups.c.group_path,
            groups.c.group_id,
            groups.c.url,
            groups.c.parent_group_path,
            groups.c.last_synced
        )
    )
    group_dict = {}
    for row in gps:
        group_dict[row["group_path"]] = {
            "id": row["group_id"],
            "name": row["name"],
            "group_path": row["group_path"],
            "url": row["url"],
            "last_synced": str(row["last_synced"]),
            "subgroups": [],
            "parent_group_path": row["parent_group_path"],
        }
    tree = []
    for group in group_dict.values():
        parent_path = group.pop("parent_group_path")
        if parent_path and parent_path in group_dict:
            group_dict[parent_path]["subgroups"].append(group)
        else:
            tree.append(group)
    return [GroupsOut(**g) for g in tree]