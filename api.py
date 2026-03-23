from typing import List, Dict
import logging

from fastapi import APIRouter, HTTPException, Query
from schemas import GroupInput, RepositoryOut, GroupTree, GroupsOut
from sync import sync_all_groups, sync_group, get_group_tree, find_repo, search_repositories, get_groups_list
from gitlab_clients import GroupNotFoundError, GitlabAPIError
from typing import List, Optional

logger = logging.getLogger("app.api")
router = APIRouter()

@router.post(
    "/api/collect",
    response_model=List[RepositoryOut],
    summary="Собрать инфу о группе"
)
async def collect_repos(group: GroupInput):
    try:
        return await sync_group(group.group_path)
    except GroupNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitlabAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in /collect")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post(
    "/api/sync",
    response_model=Dict[str, str],
    summary="Триггер полной синхронизации групп"
)
async def sync_now():
    try:
        await sync_all_groups()
        return {"status": "ok"}
    except GitlabAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        logger.exception("Unexpected error in /sync")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get(
    "/api/group-tree/{group_path:path}",
    response_model=GroupTree,
    summary="Получить дерево группы с подгруппами и репозиториями"
)
async def group_tree(group_path: str):
    tree = await get_group_tree(group_path)
    if not tree:
        raise HTTPException(status_code=404, detail="Group not found")
    return tree

@router.get(
    "/api/repo/{group_path:path}/{repo_name}",
    response_model=RepositoryOut,
    summary="Получить информацию о репозитории по пути"
)
async def get_repository(group_path: str, repo_name: str):
    row = await find_repo(group_path, repo_name)
    if not row:
        await sync_group(group_path)
        row = await find_repo(group_path, repo_name)
        if not row:
            raise HTTPException(status_code=404, detail="Repository not found")
    return row

@router.get(
    "/api/repo-search",
    response_model=List[RepositoryOut],
    summary="Поиск репозиториев по имени и/или repo_id"
)
async def repo_search(
    name: Optional[str] = Query(None, description="Имя репозитория"),
    repo_id: Optional[int] = Query(None, description="repo_id репозитория")
):
    return await search_repositories(name=name, repo_id=repo_id)

@router.get(
    "/api/groups-list",
    response_model=List[GroupsOut],
    summary="Получить список групп из БД"
)
async def groups_list():
    return await get_groups_list()
