import json
import sys
from enum import Enum
from pathlib import Path
from typing import List


# The intent of Format, RepoEntry and List[RepoEntry] is that no other
# parts of the codebase knows that json is used as the on-disk format, or know
# any of the field names.

# Version numbers will be encoded in the format from '3' onwards.
class Format(Enum):
    Lock = 1
    Manifest = 2

    @staticmethod
    def from_path(path: Path):
        if path.name == "wit-lock.json":
            return Format.Lock
        if path.name == "wit-workspace.json" or path.name == "wit-manifest.json":
            return Format.Manifest
        raise Exception("Unknown format for {}".format(str(path)))


class RepoEntry:
    def __init__(self, checkout_path, revision, remote_url, message=None):
        # The path to checkout at within the workspace.
        # JSON field name is 'name'.
        self.checkout_path = checkout_path

        # Desired revision that exists in the history of the below remote.
        # JSON field name is 'commit'
        self.revision = revision

        # Url (or local fs path) for git to clone/fetch/push.
        # JSON field name is 'source'
        self.remote_url = remote_url

        # A comment to leave in any serialized artifacts.
        # Optional. JSON field name is '//'
        self.message = message

    def __repr__(self):
        return str(self.__dict__)


# OriginalEntry encodes the RepoEntry for both Lock and Manifest formats.
class OriginalEntry():
    @staticmethod
    def to_dict(entry: RepoEntry) -> dict:
        d = {
            "name": entry.checkout_path,
            "commit": entry.revision,
            "source": entry.remote_url,
        }
        if entry.message:
            d["//"] = entry.message
        return d

    @staticmethod
    def from_dict(data: dict) -> RepoEntry:
        return RepoEntry(data["name"],
                         data["commit"],
                         data.get("source"),  # 'repo path' cli option needs this optional
                         data.get("//"))  # optional


# Utilities for List[RepoEntry]
class RepoEntries:
    @staticmethod
    def write(path: Path, entries: List[RepoEntry]):
        fmt = Format.from_path(path)
        if fmt is Format.Manifest:
            manifest_data = [OriginalEntry.to_dict(e) for e in entries]
            json_data = json.dumps(manifest_data, sort_keys=True, indent=4) + "\n"
        if fmt is Format.Lock:
            lock_data = dict((e.checkout_path, OriginalEntry.to_dict(e)) for e in entries)
            json_data = json.dumps(lock_data, sort_keys=True, indent=4) + "\n"
        path.write_text(json_data)

    @staticmethod
    def read(path: Path) -> List[RepoEntry]:
        text = path.read_text()
        # 'parse' has to be decoupled from 'read' as sometimes
        # we read files directly from the git object store rather
        # than the filesystem
        return RepoEntries.parse(text, path, "")

    @staticmethod
    def parse(text: str, path: Path, rev: str) -> List[RepoEntry]:
        try:
            fromtext = json.loads(text)
        except json.JSONDecodeError as e:
            print("Failed to parse json in {}:{}: {}".format(path, rev, e.msg))
            sys.exit(1)

        entries = []
        fmt = Format.from_path(path)
        if fmt is Format.Manifest:
            for entry in fromtext:
                entries.append(OriginalEntry.from_dict(entry))
        if fmt is Format.Lock:
            for _, entry in fromtext.items():
                entries.append(OriginalEntry.from_dict(entry))

        # Check for duplicates
        names = [entry.checkout_path for entry in entries]
        if len(names) != len(set(names)):
            dup = set([x for x in names if names.count(x) > 1])
            print("Two repositories have same checkout path in {}:{}: {}".format(path, rev, dup))
            sys.exit(1)

        return entries
