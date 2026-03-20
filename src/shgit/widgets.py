from __future__ import annotations
from textual.widgets import ListItem, ListView, Static
from rich.text import Text
from rich.syntax import Syntax
from rich.console import Group
from .git_service import BranchInfo, CommitInfo, FileStatus

class StatusPane(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Status"
    
    def update_status(self, branch: str, repo_path: str) -> None:
        repo_name = repo_path.split('/')[-1]
        status_text = Text()
        status_text.append("✓ ", style="green")
        status_text.append(f"{repo_name} → {branch}", style="white")
        self.update(status_text)

class StagedPane(ListView):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Staged Changes"
        self.show_cursor = False
    
    def update_files(self, files: list[FileStatus]) -> None:
        self.clear()
        staged_files = [f for f in files if f.staged]
        if not staged_files:
            self.append(ListItem(Static(Text("No staged files", style="dim white"))))
            return
        
        for f in staged_files:
            text = Text()
            style = "green" if f.status in ["modified", "staged"] else "red" if f.status == "deleted" else "blue"
            text.append(f"{f.status[0].upper()} ", style=style)
            text.append(f.path, style="white")
            self.append(ListItem(Static(text)))

class ChangesPane(ListView):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Changes"
        self.show_cursor = False

    def update_files(self, files: list[FileStatus]) -> None:
        self.clear()
        unstaged = [f for f in files if f.unstaged or f.status == "untracked"]
        if not unstaged:
            self.append(ListItem(Static(Text("No changed files", style="dim white"))))
            return
        
        for f in unstaged:
            text = Text()
            char = "U" if f.status == "untracked" else f.status[0].upper()
            color = "cyan" if f.status == "untracked" else "yellow"
            text.append(f"{char} ", style=color)
            text.append(f.path, style="white")
            self.append(ListItem(Static(text)))

class BranchesPane(ListView):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Local branches"
    
    def set_branches(self, branches: list[BranchInfo], current_branch: str) -> None:
        self.clear()
        for branch in branches:
            text = Text()
            is_current = branch.name == current_branch
            text.append("* " if is_current else "  ", style="green")
            text.append(branch.name, style="white")
            item = ListItem(Static(text))
            if is_current:
                item.add_class("current-branch")
            self.append(item)

class CommitsPane(ListView):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Commits"
        self._parent_app = None
        self._last_index = None
        self._last_highlighted = None

    def watch_index(self, index: int | None) -> None:
        self._update_patch_for_index(index)
        self._update_highlighting(index)

    def watch_highlighted(self, highlighted: int | None) -> None:
        if highlighted is not None:
            self._update_patch_for_index(highlighted)
            self._update_highlighting(highlighted)

    def _update_highlighting(self, index: int | None) -> None:
        if self._last_highlighted is not None and self._last_highlighted < len(self.children):
            self.children[self._last_highlighted].remove_class("highlighted-commit")
        if index is not None and index < len(self.children):
            item = self.children[index]
            item.add_class("highlighted-commit")
            self._last_highlighted = index

    def _update_patch_for_index(self, index: int | None) -> None:
        if index is not None and index != self._last_index and self._parent_app:
            self._last_index = index
            self._parent_app.selected_commit_index = index
            self._parent_app.show_commit_diff(index)

    def set_commits(self, commits: list[CommitInfo]) -> None:
        self.clear()
        self._last_highlighted = None
        for commit in commits:
            text = Text()
            text.append(commit.sha[:8], style="cyan")
            text.append(f" {commit.summary[:50]}", style="white")
            self.append(ListItem(Static(text)))

class StashPane(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Stash"

    def update_stash(self, count: int) -> None:
        self.update(Text(f"-{count} of {count}-", style="white"))

class PatchPane(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Patch"

    def show_commit_info(self, commit: CommitInfo, diff_text: str) -> None:
        header = f"commit {commit.sha}\nAuthor: {commit.author}\nDate: {commit.timestamp}\n\n{commit.summary}\n\n"
        if diff_text and diff_text != "<root commit>":
            syntax = Syntax(diff_text, "diff", theme="monokai")
            self.update(Group(Text(header, style="white"), syntax))
        else:
            self.update(Text(header + (diff_text or "No diff"), style="white"))

class CommandLogPane(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Command log"

    def update_log(self, message: str) -> None:
        text = Text("Press '@' to toggle\n", style="dim white")
        text.append(message, style="white")
        self.update(text)