from pydantic import BaseModel
from typing import List

class GroupInput(BaseModel):
    group_path: str

class RepositoryOut(BaseModel):
    repo_id: int
    name: str
    url: str
    group_path: str
    group_id: int
class GroupsOut(BaseModel):
    id: int
    name: str
    group_path: str
    url: str
    last_synced: str
    subgroups: List["GroupsOut"] = []
class GroupTree(BaseModel):
    id: int
    name: str
    url: str
    subgroups: List["GroupTree"] = []
    repositories: List[RepositoryOut] = []

GroupTree.update_forward_refs()
