from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SearchProvider(Protocol):
    def search(self, query: str, top_k: int) -> list[dict]:
        ...


@runtime_checkable
class RetrievalProvider(Protocol):
    def retrieve(
        self,
        *,
        query: str,
        uploaded_files: list[str] | None = None,
        top_k: int = 4,
    ) -> dict:
        ...


@runtime_checkable
class FetchProvider(Protocol):
    def fetch(self, url: str, **kwargs) -> dict:
        ...


@runtime_checkable
class ExecutionProvider(Protocol):
    def execute(
        self,
        *,
        command: list[str],
        cwd: str | None = None,
        timeout_seconds: int = 10,
        env: dict[str, str] | None = None,
    ) -> dict:
        ...
