from __future__ import annotations
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Container, ScrollableContainer
from textual.widgets import Footer, Header, ListView
from textual.reactive import reactive
from textual.binding import Binding

from .git_service import GitService
from .widgets import (
    StatusPane, StagedPane, ChangesPane, BranchesPane, 
    CommitsPane, StashPane, PatchPane, CommandLogPane
)

class ShgitApp(App):
    CSS_PATH = "styles.tcss"  

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "down", "Down"),
        Binding("k", "up", "Up"),
        Binding("@", "toggle_command_log", "Toggle Log"),
    ]

    active_branch: reactive[str | None] = reactive(None)
    selected_commit_index: reactive[int] = reactive(0)

    def __init__(self, repo_dir: str = ".") -> None:
        super().__init__()
        self.git = GitService(repo_dir)
        self.repo_path = repo_dir
        self.branches = []
        self.commits = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Container(id="left-column"):
                self.status_pane = StatusPane(id="status-pane")
                self.staged_pane = StagedPane(id="staged-pane")
                self.changes_pane = ChangesPane(id="changes-pane")
                self.branches_pane = BranchesPane(id="branches-pane")
                self.commits_pane = CommitsPane(id="commits-pane")
                self.stash_pane = StashPane(id="stash-pane")

                yield self.status_pane
                with Horizontal(id="files-container"):
                    yield self.staged_pane
                    yield self.changes_pane
                yield self.branches_pane
                yield self.commits_pane
                yield self.stash_pane

            with Container(id="right-column"):
                with ScrollableContainer(id="patch-scroll-container"):
                    self.patch_pane = PatchPane(id="patch-pane")
                    yield self.patch_pane
                self.command_log_pane = CommandLogPane(id="command-log-pane")
                yield self.command_log_pane
        yield Footer()

    def on_mount(self) -> None:
        self.commits_pane._parent_app = self
        self.refresh_data()

    def action_refresh(self) -> None:
        self.refresh_data()

    def action_down(self) -> None:
        if self.commits_pane.has_focus:
            self.commits_pane.index = min((self.commits_pane.index or 0) + 1, len(self.commits) - 1)
        elif self.branches_pane.has_focus:
            self.branches_pane.index = min((self.branches_pane.index or 0) + 1, len(self.branches) - 1)

    def action_up(self) -> None:
        if self.commits_pane.has_focus:
            self.commits_pane.index = max((self.commits_pane.index or 0) - 1, 0)
        elif self.branches_pane.has_focus:
            self.branches_pane.index = max((self.branches_pane.index or 0) - 1, 0)

    def refresh_data(self) -> None:
        self.branches = self.git.list_branches()
        if self.branches:
            self.active_branch = self.branches[0].name
            self.load_commits(self.active_branch)
            self.update_ui()

    def update_ui(self) -> None:
        if self.active_branch:
            self.status_pane.update_status(self.active_branch, self.repo_path)
        files = self.git.get_file_status()
        self.staged_pane.update_files(files)
        self.changes_pane.update_files(files)
        self.branches_pane.set_branches(self.branches, self.active_branch)
        self.stash_pane.update_stash(0)

    def load_commits(self, branch: str) -> None:
        self.commits = self.git.list_commits(branch)
        self.commits_pane.set_commits(self.commits)
        if self.commits:
            self.show_commit_diff(0)

    def show_commit_diff(self, index: int) -> None:
        if 0 <= index < len(self.commits):
            ci = self.commits[index]
            diff = self.git.get_commit_diff(ci.sha)
            self.patch_pane.show_commit_info(ci, diff)
    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view is self.branches_pane:
            index = event.index
            if 0 <= index < len(self.branches):
                self.active_branch = self.branches[index].name
                self.load_commits(self.active_branch)
                self.update_status_info()
        elif event.list_view is self.commits_pane:
            self.selected_commit_index = event.index
            self.show_commit_diff(event.index)

def run_textual(repo_dir: str = ".") -> None:
    app = ShgitApp(repo_dir)
    app.run()

