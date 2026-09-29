import os
from pathlib import Path
from typing import Any, Dict, List
from jarvis.config import DOCUMENTS_DIR, BASE_DIR
from jarvis.tools.registry import register_tool

def _resolve_safe_path(filepath: str) -> Path:
    """Resolve path safely, defaulting relative paths to documents directory or workspace."""
    p = Path(filepath)
    if not p.is_absolute():
        # Check if in documents first, otherwise base dir
        doc_path = DOCUMENTS_DIR / filepath
        if doc_path.exists() or not (BASE_DIR / filepath).exists():
            return doc_path
        return BASE_DIR / filepath
    return p


@register_tool(
    name="read_file",
    description="Read the contents of a local text or document file.",
    parameters={
        "filepath": {"type": "string", "description": "Path or filename to read", "required": True}
    }
)
def read_file(filepath: str) -> Dict[str, Any]:
    """Read contents of a file."""
    path = _resolve_safe_path(filepath)
    if not path.exists():
        return {"success": False, "error": f"File '{filepath}' not found at {path}."}
    if not path.is_file():
        return {"success": False, "error": f"Path '{filepath}' is a directory, not a file."}

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        # Truncate if excessively huge
        if len(content) > 10000:
            content_preview = content[:10000] + f"\n\n... [Content truncated, total length {len(content)} characters]"
        else:
            content_preview = content
        return {
            "success": True,
            "filename": path.name,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "content": content_preview
        }
    except Exception as e:
        return {"success": False, "error": f"Failed reading file: {str(e)}"}


@register_tool(
    name="list_files",
    description="List files and folders in a specified directory (defaults to documents directory).",
    parameters={
        "directory": {"type": "string", "description": "Directory path or leave empty for documents directory", "required": False}
    }
)
def list_files(directory: str = "") -> Dict[str, Any]:
    """List directory contents."""
    if not directory or directory.strip() in ("", ".", "documents", "docs"):
        target_dir = DOCUMENTS_DIR
    else:
        target_dir = _resolve_safe_path(directory)

    if not target_dir.exists():
        return {"success": False, "error": f"Directory '{directory}' does not exist."}

    try:
        items = []
        for entry in os.scandir(target_dir):
            items.append({
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size_bytes": entry.stat().st_size if entry.is_file() else None
            })
        return {
            "success": True,
            "directory": str(target_dir),
            "total_items": len(items),
            "items": items
        }
    except Exception as e:
        return {"success": False, "error": f"Failed listing directory: {str(e)}"}


@register_tool(
    name="create_document",
    description="Create a new document, note, or file with given text content.",
    parameters={
        "filename": {"type": "string", "description": "Name of the file (e.g. 'meeting_notes.txt', 'project_plan.md')", "required": True},
        "content": {"type": "string", "description": "The text content of the document", "required": True}
    }
)
def create_document(filename: str, content: str) -> Dict[str, Any]:
    """Create or overwrite a document."""
    # Ensure it's placed in DOCUMENTS_DIR if filename is simple
    path = DOCUMENTS_DIR / Path(filename).name
    try:
        path.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "message": f"Document '{path.name}' successfully created.",
            "path": str(path),
            "character_count": len(content)
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to create document: {str(e)}"}


@register_tool(
    name="append_document",
    description="Append text or notes to an existing document.",
    parameters={
        "filename": {"type": "string", "description": "Filename of the document to append to", "required": True},
        "content": {"type": "string", "description": "Text to append at the end of the document", "required": True}
    }
)
def append_document(filename: str, content: str) -> Dict[str, Any]:
    """Append text to an existing document."""
    path = DOCUMENTS_DIR / Path(filename).name
    try:
        existing = ""
        if path.exists():
            existing = path.read_text(encoding="utf-8", errors="replace")
        new_content = existing + ("\n" if existing and not existing.endswith("\n") else "") + content
        path.write_text(new_content, encoding="utf-8")
        return {
            "success": True,
            "message": f"Successfully appended content to '{path.name}'.",
            "path": str(path),
            "total_size": len(new_content)
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to append to document: {str(e)}"}


@register_tool(
    name="delete_file",
    description="Permanently delete a file. (DANGEROUS ACTION: Requires user authorization).",
    parameters={
        "filepath": {"type": "string", "description": "Path or filename to delete", "required": True}
    },
    requires_confirmation=True,
    dangerous=True
)
def delete_file(filepath: str) -> Dict[str, Any]:
    """Delete a file permanently."""
    path = _resolve_safe_path(filepath)
    if not path.exists():
        return {"success": False, "error": f"File '{filepath}' not found."}
    try:
        if path.is_file():
            path.unlink()
            return {"success": True, "message": f"File '{path.name}' has been permanently deleted."}
        else:
            return {"success": False, "error": f"Path '{filepath}' is a directory. Refusing to delete directory."}
    except Exception as e:
        return {"success": False, "error": f"Failed deleting file: {str(e)}"}
