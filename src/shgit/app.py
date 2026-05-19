from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, ListView

from .git_service import GitService
from .widgets import (
    BranchesPane,
    ChangesPane,
    CommandLogPane,
    CommitsPane,
    PatchPane,
    StagedPane,
    StashPane,
    StatusPane,
)


class CommitModal(ModalScreen[str]):
    """A pop-up modal dialog to safely capture a commit message from the user."""

    CSS = """
    CommitModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.5);
    }
    #commit-dialog {
        padding: 1 2;
        background: #2d2d2d;
        border: thick green;
        width: 60;
        height: auto;
    }
    /* We moved the bold white styling for the label here! */
    #commit-dialog Label {
        color: white;
        text-style: bold;
    }
    #message-input {
        margin-top: 1;
        border: solid white;
    }
    #message-input:focus {
        border: solid green;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="commit-dialog"):
            yield Label("Enter commit message:")
            yield Input(
                placeholder="e.g., fix: resolve index out of bounds", id="message-input"
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value:
            self.dismiss(value)
        else:
            self.dismiss("")


class ShgitApp(App):
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "down", "Down"),
        Binding("k", "up", "Up"),
        Binding("s", "stage", "Stage File"),
        Binding("u", "unstage", "Unstage File"),
        Binding("c", "commit", "Commit"),
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
            self.commits_pane.index = min(
                (self.commits_pane.index or 0) + 1, len(self.commits) - 1
            )
        elif self.branches_pane.has_focus:
            self.branches_pane.index = min(
                (self.branches_pane.index or 0) + 1, len(self.branches) - 1
            )
        elif self.changes_pane.has_focus:
            self.changes_pane.index = (self.changes_pane.index or 0) + 1
        elif self.staged_pane.has_focus:
            self.staged_pane.index = (self.staged_pane.index or 0) + 1

    def action_up(self) -> None:
        if self.commits_pane.has_focus:
            self.commits_pane.index = max((self.commits_pane.index or 0) - 1, 0)
        elif self.branches_pane.has_focus:
            self.branches_pane.index = max((self.branches_pane.index or 0) - 1, 0)
        elif self.changes_pane.has_focus:
            self.changes_pane.index = max((self.changes_pane.index or 0) - 1, 0)
        elif self.staged_pane.has_focus:
            self.staged_pane.index = max((self.staged_pane.index or 0) - 1, 0)

    def action_toggle_command_log(self) -> None:
        """Toggles the visibility of the Command Log panel."""
        self.command_log_pane.visible = not self.command_log_pane.visible

    def action_stage(self) -> None:
        """Stages the currently highlighted file in the Changes pane."""
        if not self.changes_pane.has_focus:
            return

        current_item = self.changes_pane.highlighted_child
        if not current_item or not hasattr(current_item, "file_data"):
            return

        file_to_stage = current_item.file_data
        try:
            self.git.stage_file(file_to_stage.path)
            self.command_log_pane.update_log(f"Staged: {file_to_stage.path}")
            self.refresh_data()
        except Exception as e:
            self.command_log_pane.update_log(f"Staging failed: {str(e)}")

    def action_unstage(self) -> None:
        """Unstages the currently highlighted file in the Staged pane."""
        if not self.staged_pane.has_focus:
            return

        current_item = self.staged_pane.highlighted_child
        if not current_item or not hasattr(current_item, "file_data"):
            return

        file_to_unstage = current_item.file_data
        try:
            self.git.unstage_file(file_to_unstage.path)
            self.command_log_pane.update_log(f"Unstaged: {file_to_unstage.path}")
            self.refresh_data()
        except Exception as e:
            self.command_log_pane.update_log(f"Unstaging failed: {str(e)}")

    def action_commit(self) -> None:
        """Evaluates staged inventory and requests a commit message via Modal."""
        files = self.git.get_file_status()

        if not any(f.staged for f in files):
            self.command_log_pane.update_log(
                "Error: No changes added to commit (staging area empty)."
            )
            return

        def handle_commit_submission(message: str | None) -> None:
            if not message:
                self.command_log_pane.update_log("Commit cancelled.")
                return

            try:
                new_sha = self.git.commit(
                    message=message, author="TUI User <user@example.com>"
                )
                self.command_log_pane.update_log(
                    f"Successfully committed! SHA: {new_sha[:7]}"
                )
                self.refresh_data()
            except Exception as e:
                self.command_log_pane.update_log(f"Commit failed: {str(e)}")

        self.push_screen(CommitModal(), handle_commit_submission)

    def refresh_data(self) -> None:
        self.branches = self.git.list_branches()
        if self.branches:
            if not self.active_branch:
                self.active_branch = self.branches[0].name

            self.load_commits(self.active_branch)
            self.update_ui()

    def update_ui(self) -> None:
        if self.active_branch:
            self.status_pane.update_status(self.active_branch, self.repo_path)
        files = self.git.get_file_status()
        self.staged_pane.update_files(files)
        self.changes_pane.update_files(files)
        self.branches_pane.set_branches(self.branches, self.active_branch or "")
        self.stash_pane.update_stash(0)

    def load_commits(self, branch: str) -> None:
        self.commits = self.git.list_commits(branch)
        self.commits_pane.set_commits(self.commits)
        if self.commits:
            self.show_commit_diff(0)

    def update_status_info(self) -> None:
        if self.active_branch:
            self.status_pane.update_status(self.active_branch, self.repo_path)

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
