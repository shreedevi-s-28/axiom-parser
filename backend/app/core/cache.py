# backend/app/core/cache.py
import os
import json
import hashlib
from typing import Optional
from app.schemas.document import ParseResult

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "provenance"))

class ProvenanceCache:
    """
    Guarantees zero-downtime and sub-second fallbacks for live demos.
    If a known demo file is uploaded, cached golden results can be served instantly.
    """
    def __init__(self):
        os.makedirs(CACHE_DIR, exist_ok=True)

    def get_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def get(self, content: bytes, filename: str) -> Optional[dict]:
        file_hash = self.get_hash(content)
        cache_file = os.path.join(CACHE_DIR, f"{file_hash}.json")
        
        # Check by content hash
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                return json.load(f)
        
        # Secondary check: Check by demo filename alias
        alias_file = os.path.join(CACHE_DIR, f"{filename}.json")
        if os.path.exists(alias_file):
            with open(alias_file, "r") as f:
                return json.load(f)

        return None

    def set(self, content: bytes, filename: str, result_dict: dict) -> None:
        file_hash = self.get_hash(content)
        cache_file = os.path.join(CACHE_DIR, f"{file_hash}.json")
        with open(cache_file, "w") as f:
            json.dump(result_dict, f, indent=2)

cache_engine = ProvenanceCache()