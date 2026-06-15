from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from dulwich import porcelain
from dulwich.errors import NotGitRepository
from dulwich.objects import Commit
from dulwich.repo import Repo


@dataclass
class BranchInfo:
    name: str
    head_sha: str


@dataclass
class CommitInfo:
    sha: str
    summary: str
    author: str
    timestamp: int


@dataclass
class FileStatus:
    path: str
    status: str
    staged: bool
    unstaged: bool = False


class GitService:
    def __init__(self, start_dir: Path | str = ".") -> None:
        self.repo_path = self._find_repo_root(Path(start_dir))
        self.repo = Repo(str(self.repo_path))

    @staticmethod
    def _find_repo_root(path: Path) -> Path:
        current = path.resolve()
        while True:
            git_dir = current / ".git"
            if git_dir.exists() and git_dir.is_dir():
                return current
            if current.parent == current:
                raise NotGitRepository(f"No .git found from {path}")
            current = current.parent

    def _is_ignored(self, file_path: str) -> bool:
        """Check if a file is ignored by .gitignore rules."""
        import fnmatch

        gitignore_path = self.repo_path / ".gitignore"
        if not gitignore_path.exists():
            return False

        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                gitignore_lines = f.readlines()
        except Exception:
            return False

        normalized_path = file_path.replace("\\", "/")
        path_parts = normalized_path.split("/")
        is_ignored = False

        for line in gitignore_lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            is_negation = line.startswith("!")
            if is_negation:
                pattern = line[1:].strip()
            else:
                pattern = line

            if not pattern:
                continue

            pattern = pattern.rstrip("/")
            fnmatch_pattern = pattern.replace("**", "*")

            if pattern.startswith("/"):
                pattern = pattern[1:]
                fnmatch_pattern = fnmatch_pattern[1:]

                if fnmatch.fnmatch(
                    normalized_path, fnmatch_pattern
                ) or normalized_path.startswith(pattern + "/"):
                    is_ignored = not is_negation
            else:
                matched = False
                if fnmatch.fnmatch(normalized_path, fnmatch_pattern):
                    matched = True

                for i in range(len(path_parts)):
                    check_path = "/".join(path_parts[i:])
                    if fnmatch.fnmatch(check_path, fnmatch_pattern) or fnmatch.fnmatch(
                        path_parts[i], fnmatch_pattern
                    ):
                        matched = True
                        break

                if matched:
                    is_ignored = not is_negation

        return is_ignored

    def list_branches(self) -> List[BranchInfo]:
        heads = self.repo.refs.as_dict(b"refs/heads")
        result: List[BranchInfo] = []
        for ref, sha in heads.items():
            name = ref.decode().split("/heads/")[-1]
            result.append(BranchInfo(name=name, head_sha=sha.hex()))
        result.sort(key=lambda b: b.name.lower())
        return result

    def _iter_commits(
        self, head_sha: bytes, max_count: int = 100
    ) -> Iterable[Tuple[bytes, Commit]]:
        seen = set()
        stack = [head_sha]
        while stack and len(seen) < max_count:
            sha = stack.pop(0)
            if sha in seen:
                continue
            seen.add(sha)
            commit: Commit = self.repo[sha]
            yield sha, commit
            stack.extend(commit.parents)

    def list_commits(self, branch: str, max_count: int = 200) -> List[CommitInfo]:
        ref = f"refs/heads/{branch}".encode()
        try:
            head = self.repo.refs[ref]
        except KeyError:
            return []

        commits: List[CommitInfo] = []
        for sha, commit in self._iter_commits(head, max_count=max_count):
            author = (
                commit.author.decode(errors="replace")
                if isinstance(commit.author, (bytes, bytearray))
                else str(commit.author)
            )
            summary = commit.message.split(b"\n", 1)[0].decode(errors="replace")
            commits.append(
                CommitInfo(
                    sha=sha.hex(),
                    summary=summary,
                    author=author,
                    timestamp=int(commit.commit_time),
                )
            )
        return commits

    def get_commit_diff(self, sha_hex: str) -> str:
        sha = bytes.fromhex(sha_hex)
        commit: Commit = self.repo[sha]
        parents = commit.parents
        if not parents:
            return "<root commit>"
        parent = self.repo[parents[0]]

        import io

        from dulwich.patch import write_tree_diff

        buf = io.BytesIO()
        write_tree_diff(buf, self.repo.object_store, parent.tree, commit.tree)
        diff_text = buf.getvalue().decode(errors="replace")
        return diff_text

    def stage_file(self, file_path: str) -> None:
        """Stages a file to the Git index (equivalent to 'git add')."""
        porcelain.add(repo=self.repo, paths=[file_path])

    def unstage_file(self, file_path: str) -> None:
        """Unstages a file from the Git index (equivalent to 'git reset HEAD <file>')."""
        porcelain.remove(repo=self.repo, paths=[file_path], cached=True)

    def commit(
        self,
        message: str,
        author: Optional[str] = None,
        committer: Optional[str] = None,
    ) -> str:
        """
        Commits currently staged changes (the index) to the repository using porcelain.

        Args:
            message: The commit message.
            author: Optional string in "Name <email>" format. Pass None to use system git config.
            committer: Optional string in "Name <email>" format (defaults to author).

        Returns:
            The hex string SHA of the newly created commit.
        """
        try:
            head_file = self.repo_path / ".git" / "HEAD"
            if head_file.exists():
                content = head_file.read_bytes().strip()
                if content == b"ref: refs/heads/":
                    head_file.write_bytes(b"ref: refs/heads/main\n")
                elif content.startswith(b"ref:"):
                    ref_line = content.split(b"\n")[0].strip()
                    head_file.write_bytes(ref_line + b"\n")
        except Exception:
            pass

        if not message.endswith("\n"):
            message += "\n"

        message_bytes = message.encode("utf-8")
        author_bytes = author.encode("utf-8") if author else None
        committer_bytes = committer.encode("utf-8") if committer else None

        try:
            commit_id: bytes = porcelain.commit(
                repo=self.repo,
                message=message_bytes,
                author=author_bytes,
                committer=committer_bytes,
            )
            return commit_id.decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Failed to create porcelain commit: {e}")

    def stage_files(self, paths: List[str]) -> None:
        """A helper method to stage multiple file paths."""
        normalized_paths = [p.replace("\\", "/") for p in paths]
        self.repo.stage(normalized_paths)

    def get_file_status(self) -> List[FileStatus]:
        """Get status of files in working directory."""
        import os

        from dulwich.index import Index
        from dulwich.objects import Blob

        files: List[FileStatus] = []

        try:
            index = Index(str(self.repo_path / ".git" / "index"))
            index_entries = {
                path.decode(errors="replace"): entry for path, entry in index.items()
            }
        except Exception:
            index_entries = {}

        def calculate_blob_sha(file_data: bytes) -> bytes:
            blob = Blob()
            blob.data = file_data
            return blob.id

        try:
            head_ref = self.repo.refs[b"HEAD"]
            head_commit = self.repo[head_ref]
            head_tree = self.repo[head_commit.tree]
        except Exception:
            head_tree = None

        processed_files = set()

        def find_in_tree(tree, path_parts):
            if not path_parts:
                return None
            name = path_parts[0].encode()
            if name in tree:
                entry_item = tree[name]
                mode, sha = entry_item
                if len(path_parts) == 1:
                    return sha
                else:
                    if stat.S_ISDIR(mode):
                        subtree_obj = self.repo[sha]
                        return find_in_tree(subtree_obj, path_parts[1:])
            return None

        for path, entry in index_entries.items():
            processed_files.add(path)
            full_path = self.repo_path / path

            if not full_path.exists():
                files.append(
                    FileStatus(path=path, status="deleted", staged=True, unstaged=False)
                )
                continue

            try:
                with open(full_path, "rb") as f:
                    file_data = f.read()
                    file_sha = calculate_blob_sha(file_data)
            except Exception:
                continue

            index_sha = entry.sha
            head_sha = None

            if head_tree:
                path_parts = path.split("/")
                try:
                    head_sha = find_in_tree(head_tree, path_parts)
                except (KeyError, TypeError):
                    head_sha = None

            if head_sha is not None:
                if head_sha != index_sha:
                    files.append(
                        FileStatus(
                            path=path, status="modified", staged=True, unstaged=False
                        )
                    )
            else:
                files.append(
                    FileStatus(path=path, status="staged", staged=True, unstaged=False)
                )

        def walk_directory(path: Path, base: Path):
            if path.name == ".git" and path.is_dir():
                return

            try:
                for item in path.iterdir():
                    if item.name.startswith("."):
                        continue

                    if item.is_dir():
                        walk_directory(item, base)
                    elif item.is_file():
                        rel_path = str(item.relative_to(base)).replace("\\", "/")

                        if rel_path not in processed_files:
                            head_sha = None
                            if head_tree:
                                path_parts = rel_path.split("/")
                                try:
                                    head_sha = find_in_tree(head_tree, path_parts)
                                except (KeyError, TypeError):
                                    head_sha = None

                            if head_sha is not None:
                                with open(item, "rb") as f:
                                    file_data = f.read()
                                    file_sha = calculate_blob_sha(file_data)

                                if head_sha != file_sha:
                                    files.append(
                                        FileStatus(
                                            path=rel_path,
                                            status="modified",
                                            staged=False,
                                            unstaged=True,
                                        )
                                    )
                            else:
                                if not self._is_ignored(rel_path):
                                    files.append(
                                        FileStatus(
                                            path=rel_path,
                                            status="untracked",
                                            staged=False,
                                            unstaged=False,
                                        )
                                    )
                        else:
                            if rel_path in index_entries:
                                entry = index_entries[rel_path]
                                try:
                                    with open(item, "rb") as f:
                                        file_data = f.read()
                                        file_sha = calculate_blob_sha(file_data)

                                    index_sha = entry.sha
                                    head_sha = None
                                    if head_tree:
                                        path_parts = rel_path.split("/")
                                        try:
                                            head_sha = find_in_tree(
                                                head_tree, path_parts
                                            )
                                        except (KeyError, TypeError):
                                            head_sha = None

                                    if index_sha != file_sha:
                                        if head_sha is None or file_sha != head_sha:
                                            if not any(
                                                f.path == rel_path and not f.staged
                                                for f in files
                                            ):
                                                files.append(
                                                    FileStatus(
                                                        path=rel_path,
                                                        status="modified",
                                                        staged=False,
                                                        unstaged=True,
                                                    )
                                                )
                                except Exception:
                                    pass
            except PermissionError:
                pass

        walk_directory(self.repo_path, self.repo_path)

        file_dict: dict[str, FileStatus] = {}
        for file_status in files:
            if file_status.path in file_dict:
                existing = file_dict[file_status.path]
                if existing.staged != file_status.staged:
                    file_dict[file_status.path] = FileStatus(
                        path=file_status.path,
                        status="modified",
                        staged=True,
                        unstaged=True,
                    )
                elif file_status.status == "modified" or existing.status != "modified":
                    file_dict[file_status.path] = file_status
            else:
                file_dict[file_status.path] = file_status

        files = list(file_dict.values())
        files_with_changes = []
        for f in files:
            if f.staged or f.unstaged or f.status in ["untracked", "deleted", "staged"]:
                if f.status == "untracked" and self._is_ignored(f.path):
                    continue
                files_with_changes.append(f)

        files_with_changes.sort(key=lambda f: f.path)
        return files_with_changes
