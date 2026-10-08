# backend/app/core/store.py
"""
Small on-disk store for uploaded PDFs so page previews can be rendered on demand.

Files live in the OS temp directory and only the most recent MAX_DOCUMENTS are kept.
"""
import os
import re
import tempfile
import threading
from typing import Optional

STORE_DIR = os.path.join(tempfile.gettempdir(), "axiomparse_documents")
MAX_DOCUMENTS = 25
_DOC_ID_PATTERN = re.compile(r"^doc_[0-9a-f]{8}$")


class DocumentStore:
    def __init__(self, directory: str = STORE_DIR, max_documents: int = MAX_DOCUMENTS):
        self.directory = directory
        self.max_documents = max_documents
        self._prune_lock = threading.Lock()
        os.makedirs(self.directory, exist_ok=True)

    @staticmethod
    def is_valid_id(document_id: str) -> bool:
        return bool(_DOC_ID_PATTERN.match(document_id))

    def _path(self, document_id: str) -> str:
        return os.path.join(self.directory, f"{document_id}.pdf")

    def save(self, document_id: str, content: bytes) -> str:
        if not self.is_valid_id(document_id):
            raise ValueError(f"Invalid document id: {document_id!r}")
        path = self._path(document_id)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def path_for(self, document_id: str) -> Optional[str]:
        if not self.is_valid_id(document_id):
            return None
        path = self._path(document_id)
        return path if os.path.exists(path) else None

    def delete(self, document_id: str) -> None:
        path = self.path_for(document_id)
        if path:
            try:
                os.remove(path)
            except OSError:
                pass

    @staticmethod
    def _mtime(path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0  # already removed by someone else

    def prune(self) -> None:
        """Keep only the newest `max_documents` files. Safe to call from several threads."""
        with self._prune_lock:
            files = [
                os.path.join(self.directory, name)
                for name in os.listdir(self.directory)
                if name.endswith(".pdf")
            ]
            files.sort(key=self._mtime, reverse=True)
            for stale in files[self.max_documents:]:
                try:
                    os.remove(stale)
                except OSError:
                    pass


document_store = DocumentStore()
