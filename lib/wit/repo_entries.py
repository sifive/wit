import json
from pathlib import Path
from typing import List


# The intent of RepoEntry and List[RepoEntry] is that no other
# parts of the codebase knows that json is used as the on-disk format, or know
# any of the field names.


class RepoEntry:

    def __init__(self, workspace_name, revision, remote_path, message=None):
        # The path to checkout at within the workspace.
        # JSON field name is 'name'.
        self.workspace_name = workspace_name

        # Desired revision that exists in the history of the below remote.
        # JSON field name is 'commit'
        self.revision = revision

        # Name of the branch that the revision is required to be a member of.
        # Optional. JSON field name is 'branch'
        # TODO add this
        # self.branch = branch

        # Url (or local fs path) for git to clone/fetch/push.
        # JSON field name is 'source'
        self.remote_path = remote_path

        # Name assigned to the remote within the repository checkout.
        # Optional. JSON field name is 'remote_name'
        # TODO add this
        # self.remote_name = remote_name

        # A comment to leave in any serialized artifacts.
        # Optional. JSON field name is '//'
        self.message = message

    def _serialized_names(self) -> dict:
        d = {
            "name": self.workspace_name,
            "commit": self.revision,
            "source": self.remote_path,
        }
        if self.message and len(self.message) > 0:
            d["//"] = self.message
        return d

    @staticmethod
    def _from_serialized_names(data: dict):
        return RepoEntry(data["name"],
                         data["commit"],
                         data.get("source"),  # 'repo path' cli option needs this optional
                         data.get("//"))  # optional

    def __repr__(self):
        return str(self.__dict__)


# Utilities for List[RepoEntry]
class RepoEntries:
    @staticmethod
    def parse_repo_entries(text: str, where: str) -> List[RepoEntry]:
        try:
            fromtext = json.loads(text)
        except json.JSONDecodeError as e:
            raise Exception("Failed to parse json in {}: {}".format(where, e.msg))

        entries = []
        for entry in fromtext:
            entries.append(RepoEntry._from_serialized_names(entry))

        # Check for duplicates
        names = [entry.workspace_name for entry in entries]
        if len(names) != len(set(names)):
            dup = set([x for x in names if names.count(x) > 1])
            raise Exception("Two repositories have the same name in {}: {}".format(where, dup))

        return entries

    @staticmethod
    def write_repo_entries(path: Path, entries: List[RepoEntry]):
        dict_data = [e._serialized_names() for e in entries]
        json_data = json.dumps(dict_data, sort_keys=True, indent=4) + "\n"
        path.write_text(json_data)

    @staticmethod
    def read_repo_entries(path: Path) -> List[RepoEntry]:
        text = path.read_text()
        return RepoEntries.parse_repo_entries(text, str(path))
