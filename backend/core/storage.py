"""Where uploaded files are kept. Today: a folder on disk. Later: S3 (same relative keys)."""
import hashlib
import uuid
from pathlib import Path

from django.conf import settings


def absolute_path(relative_path):
    """Turn a stored relative path into a real path, refusing anything outside STORAGE_ROOT."""
    root = Path(settings.STORAGE_ROOT).resolve()
    full = (root / relative_path).resolve()
    if root not in full.parents:
        raise ValueError("Path is outside the storage folder.")
    return full


def save_upload(uploaded_file, account_id, extension):
    """Write an uploaded file to disk under a random name.

    Returns (relative_path, sha256_hex, size_in_bytes).
    """
    relative = f"documents/{account_id}/{uuid.uuid4().hex}.{extension}"
    destination = absolute_path(relative)
    destination.parent.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    size = 0
    with open(destination, "wb") as out:
        for chunk in uploaded_file.chunks():
            digest.update(chunk)
            size += len(chunk)
            out.write(chunk)
    return relative, digest.hexdigest(), size


def delete_file(relative_path):
    """Delete a stored file (and its folder if it is now empty). Never raises."""
    try:
        path = absolute_path(relative_path)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass  # folder not empty
    except (ValueError, OSError):
        pass