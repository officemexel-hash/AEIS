"""
SYLION Cognitive -- Idea Attachments

File attachment management for ideas. Stores file metadata and base64-encoded
content in SQLite for self-contained portability.

Tables:
  idea_attachments

Singleton: get_idea_attachments() / reset_idea_attachments()
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import logging
import re
import sqlite3
import struct
import threading
import time
import uuid
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.cognitive.idea_attachments")


# ---------------------------------------------------------------------------
# IdeaAttachments
# ---------------------------------------------------------------------------

class IdeaAttachments:
    """File attachment storage for ideas using SQLite with base64 content.

    Thread-safe. Emits events on attachment mutations.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS idea_attachments (
                attachment_id  TEXT PRIMARY KEY,
                idea_id        TEXT NOT NULL,
                filename       TEXT NOT NULL DEFAULT '',
                file_type      TEXT NOT NULL DEFAULT 'application/octet-stream',
                file_size      INTEGER NOT NULL DEFAULT 0,
                content_b64    TEXT NOT NULL DEFAULT '',
                created_at     REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_att_idea ON idea_attachments(idea_id);
            CREATE INDEX IF NOT EXISTS idx_att_type ON idea_attachments(file_type);

            CREATE TABLE IF NOT EXISTS idea_attachment_analysis (
                analysis_id            TEXT PRIMARY KEY,
                attachment_id          TEXT NOT NULL,
                idea_id                TEXT NOT NULL,
                filename               TEXT NOT NULL DEFAULT '',
                file_type              TEXT NOT NULL DEFAULT 'application/octet-stream',
                file_size              INTEGER NOT NULL DEFAULT 0,
                content_sha256         TEXT NOT NULL DEFAULT '',
                detected_kind          TEXT NOT NULL DEFAULT 'unknown',
                extracted_text_preview TEXT NOT NULL DEFAULT '',
                tags_json              TEXT NOT NULL DEFAULT '[]',
                risks_json             TEXT NOT NULL DEFAULT '[]',
                missing_info_json      TEXT NOT NULL DEFAULT '[]',
                suggested_skills_json  TEXT NOT NULL DEFAULT '[]',
                decision_class         TEXT NOT NULL DEFAULT 'D1',
                human_gate_required    INTEGER NOT NULL DEFAULT 0,
                image_analysis_status  TEXT NOT NULL DEFAULT 'not_applicable',
                created_at             REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_att_analysis_idea
                ON idea_attachment_analysis(idea_id);
            CREATE INDEX IF NOT EXISTS idx_att_analysis_attachment
                ON idea_attachment_analysis(attachment_id);
        """)
        self._conn.commit()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.idea_attachments",
            ))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_attachment(self, idea_id: str, filename: str,
                       file_type: str, content_bytes: bytes) -> dict:
        """Add an attachment. Stores metadata and base64 content in SQLite.

        Returns attachment dict.
        """
        if not idea_id:
            raise ValueError("idea_id must not be empty")
        if not filename:
            raise ValueError("filename must not be empty")
        if not isinstance(content_bytes, bytes):
            raise TypeError("content_bytes must be bytes")

        attachment_id = self._uid()
        now = time.time()
        content_b64 = base64.b64encode(content_bytes).decode("ascii")
        file_size = len(content_bytes)

        with self._lock:
            self._conn.execute(
                "INSERT INTO idea_attachments "
                "(attachment_id, idea_id, filename, file_type, file_size, "
                "content_b64, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (attachment_id, idea_id, filename, file_type,
                 file_size, content_b64, now),
            )
            self._conn.commit()

        self._emit("attachment_added", {
            "attachment_id": attachment_id,
            "idea_id": idea_id,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
        })
        log.info("add_attachment %s for idea %s: %s (%d bytes)",
                 attachment_id[:12], idea_id[:12], filename, file_size)
        return self.get_attachment(attachment_id)

    def get_attachment(self, attachment_id: str) -> dict | None:
        """Retrieve a single attachment by ID (without base64 content)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT attachment_id, idea_id, filename, file_type, "
                "file_size, created_at FROM idea_attachments "
                "WHERE attachment_id = ?",
                (attachment_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def get_attachment_content(self, attachment_id: str) -> bytes | None:
        """Retrieve the raw bytes content of an attachment."""
        with self._lock:
            row = self._conn.execute(
                "SELECT content_b64 FROM idea_attachments "
                "WHERE attachment_id = ?",
                (attachment_id,),
            ).fetchone()
        if not row:
            return None
        return base64.b64decode(row["content_b64"])

    def _get_attachment_with_content(self, attachment_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT attachment_id, idea_id, filename, file_type, "
                "file_size, content_b64, created_at FROM idea_attachments "
                "WHERE attachment_id = ?",
                (attachment_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_attachments(self, idea_id: str) -> list[dict]:
        """List all attachments for an idea (without base64 content)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT attachment_id, idea_id, filename, file_type, "
                "file_size, created_at FROM idea_attachments "
                "WHERE idea_id = ? ORDER BY created_at DESC",
                (idea_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_attachments(self, idea_id: str) -> list[dict]:
        """Workspace-vocabulary alias for list_attachments."""
        return self.list_attachments(idea_id)

    def reassign_attachments(self, attachment_ids: list[str], target_idea_id: str) -> list[dict]:
        """Move draft-uploaded attachments onto the final Idea Vault id."""
        if not target_idea_id:
            raise ValueError("target_idea_id must not be empty")
        ids = [str(item).strip() for item in attachment_ids if str(item).strip()]
        if not ids:
            return []
        with self._lock:
            for attachment_id in ids:
                self._conn.execute(
                    "UPDATE idea_attachments SET idea_id = ? WHERE attachment_id = ?",
                    (target_idea_id, attachment_id),
                )
                self._conn.execute(
                    "UPDATE idea_attachment_analysis SET idea_id = ? WHERE attachment_id = ?",
                    (target_idea_id, attachment_id),
                )
            self._conn.commit()
        self._emit("attachments_reassigned", {
            "idea_id": target_idea_id,
            "attachment_ids": ids,
        })
        return self.list_attachments(target_idea_id)

    def delete_attachment(self, attachment_id: str) -> bool:
        """Delete an attachment. Returns True if deleted."""
        with self._lock:
            row = self._conn.execute(
                "SELECT idea_id, filename FROM idea_attachments "
                "WHERE attachment_id = ?",
                (attachment_id,),
            ).fetchone()
            if not row:
                return False

            self._conn.execute(
                "DELETE FROM idea_attachments WHERE attachment_id = ?",
                (attachment_id,),
            )
            self._conn.execute(
                "DELETE FROM idea_attachment_analysis WHERE attachment_id = ?",
                (attachment_id,),
            )
            self._conn.commit()

        self._emit("attachment_deleted", {
            "attachment_id": attachment_id,
            "idea_id": row["idea_id"],
            "filename": row["filename"],
        })
        log.info("delete_attachment %s", attachment_id[:12])
        return True

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_preview_text(text: str, *, preserve_lines: bool = False, limit: int = 0) -> str:
        text = html.unescape(text or "").replace("\x00", " ")
        if preserve_lines:
            lines = [
                re.sub(r"[ \t\r\f\v]+", " ", line).strip()
                for line in text.splitlines()
            ]
            normalized = "\n".join(line for line in lines if line)
        else:
            normalized = re.sub(r"\s+", " ", text).strip()
        if limit and len(normalized) > limit:
            return normalized[: max(0, limit - 3)].rstrip() + "..."
        return normalized

    @staticmethod
    def _extract_xml_text(xml_bytes: bytes, *, limit: int = 12000) -> str:
        try:
            root = ET.fromstring(xml_bytes)
            text = " ".join(part for part in root.itertext() if part)
        except ET.ParseError:
            raw = xml_bytes.decode("utf-8", errors="replace")
            text = re.sub(r"<[^>]+>", " ", raw)
        return IdeaAttachments._normalize_preview_text(text, limit=limit)

    @staticmethod
    def _read_ooxml_members(content: bytes, prefixes: tuple[str, ...], *, limit: int = 16000) -> list[tuple[str, str]]:
        parts: list[tuple[str, str]] = []
        budget = limit
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = sorted(
                name for name in archive.namelist()
                if name.endswith(".xml") and any(name.startswith(prefix) for prefix in prefixes)
            )
            for name in names:
                if budget <= 0:
                    break
                try:
                    raw = archive.read(name)
                except (KeyError, OSError, RuntimeError, zipfile.BadZipFile):
                    continue
                text = IdeaAttachments._extract_xml_text(raw, limit=min(4000, budget))
                if not text:
                    continue
                parts.append((name, text))
                budget -= len(text)
        return parts

    @staticmethod
    def _extract_docx_text(content: bytes) -> str:
        try:
            parts = IdeaAttachments._read_ooxml_members(
                content,
                (
                    "word/document.xml",
                    "word/header",
                    "word/footer",
                    "word/footnotes",
                    "word/endnotes",
                    "word/comments",
                ),
                limit=18000,
            )
        except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
            return f"DOCX document analysis: parser_error={type(exc).__name__}; text extraction failed."
        lines = [f"DOCX document analysis: xml_parts_with_text={len(parts)}."]
        if parts:
            lines.append("Extracted text:")
            for name, text in parts[:16]:
                lines.append(f"- {name}: {text}")
        else:
            lines.append("No readable document text found; file may be empty, protected or image-only.")
        return "\n".join(lines)

    @staticmethod
    def _extract_pptx_text(content: bytes) -> str:
        try:
            parts = IdeaAttachments._read_ooxml_members(
                content,
                ("ppt/slides/slide", "ppt/notesSlides/notesSlide", "ppt/comments"),
                limit=18000,
            )
        except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
            return f"PPTX presentation analysis: parser_error={type(exc).__name__}; text extraction failed."
        lines = [f"PPTX presentation analysis: slides_or_notes_with_text={len(parts)}."]
        if parts:
            lines.append("Extracted slide text:")
            for name, text in parts[:30]:
                slide = Path(name).stem
                lines.append(f"- {slide}: {text}")
        else:
            lines.append("No readable slide text found; presentation may be image-only.")
        return "\n".join(lines)

    @staticmethod
    def _extract_xlsx_text(content: bytes) -> str:
        try:
            parts = IdeaAttachments._read_ooxml_members(
                content,
                ("xl/sharedStrings", "xl/workbook", "xl/worksheets/sheet"),
                limit=18000,
            )
        except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
            return f"XLSX workbook analysis: parser_error={type(exc).__name__}; text extraction failed."
        lines = [f"XLSX workbook analysis: xml_parts_with_values={len(parts)}."]
        if parts:
            lines.append("Extracted cells/labels:")
            for name, text in parts[:24]:
                lines.append(f"- {name}: {text}")
        else:
            lines.append("No readable workbook strings found; workbook may contain only numeric or protected data.")
        return "\n".join(lines)

    @staticmethod
    def _extract_pdf_text(content: bytes) -> str:
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(io.BytesIO(content))
            page_count = len(reader.pages)
            metadata = {}
            try:
                metadata = {
                    str(key).lstrip("/"): str(value)
                    for key, value in (reader.metadata or {}).items()
                    if value is not None
                }
            except Exception:  # noqa: BLE001
                metadata = {}
            text_parts: list[str] = []
            budget = 18000
            for index, page in enumerate(reader.pages[:20], start=1):
                if budget <= 0:
                    break
                try:
                    page_text = page.extract_text() or ""
                except Exception:  # noqa: BLE001
                    page_text = ""
                page_text = IdeaAttachments._normalize_preview_text(page_text, limit=min(3500, budget))
                if not page_text:
                    continue
                text_parts.append(f"- page {index}: {page_text}")
                budget -= len(page_text)
            lines = [
                f"PDF document analysis: pages={page_count}; encrypted={bool(getattr(reader, 'is_encrypted', False))}; "
                f"metadata_keys={', '.join(sorted(metadata)[:8]) or 'none'}.",
            ]
            if metadata:
                meta_preview = "; ".join(f"{key}={value}" for key, value in list(metadata.items())[:8])
                lines.append(f"Metadata preview: {meta_preview}")
            if text_parts:
                lines.append("Extracted text:")
                lines.extend(text_parts)
            else:
                lines.append("No extractable text found; OCR or a vision-capable model is required for scanned pages.")
            return "\n".join(lines)
        except Exception as exc:  # noqa: BLE001
            return f"PDF document analysis: parser_error={type(exc).__name__}; text extraction/OCR required."

    @staticmethod
    def _jpeg_dimensions(content: bytes) -> tuple[int, int] | None:
        index = 2
        while index + 9 < len(content):
            if content[index] != 0xFF:
                index += 1
                continue
            marker = content[index + 1]
            index += 2
            if marker in {0xD8, 0xD9, 0x01}:
                continue
            if index + 2 > len(content):
                return None
            length = struct.unpack(">H", content[index:index + 2])[0]
            if length < 2 or index + length > len(content):
                return None
            if 0xC0 <= marker <= 0xC3 or 0xC5 <= marker <= 0xC7 or 0xC9 <= marker <= 0xCB or 0xCD <= marker <= 0xCF:
                if index + 7 <= len(content):
                    height, width = struct.unpack(">HH", content[index + 3:index + 7])
                    return int(width), int(height)
            index += length
        return None

    @staticmethod
    def _fallback_image_dimensions(content: bytes) -> tuple[str, int | None, int | None]:
        if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
            width, height = struct.unpack(">II", content[16:24])
            return "PNG", int(width), int(height)
        if content.startswith((b"GIF87a", b"GIF89a")) and len(content) >= 10:
            width, height = struct.unpack("<HH", content[6:10])
            return "GIF", int(width), int(height)
        if content.startswith(b"\xff\xd8"):
            dims = IdeaAttachments._jpeg_dimensions(content)
            if dims:
                return "JPEG", dims[0], dims[1]
            return "JPEG", None, None
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return "WEBP", None, None
        return "unknown", None, None

    @staticmethod
    def _summarize_image(content: bytes) -> str:
        try:
            from PIL import Image  # type: ignore

            with Image.open(io.BytesIO(content)) as image:
                frames = getattr(image, "n_frames", 1)
                exif_count = 0
                try:
                    exif_count = len(image.getexif() or {})
                except Exception:  # noqa: BLE001
                    exif_count = 0
                return (
                    "Image file analysis: "
                    f"format={image.format or 'unknown'}; width_px={image.width}; height_px={image.height}; "
                    f"mode={image.mode}; frames={frames}; exif_entries={exif_count}. "
                    "Semantic content, screenshots and OCR require a configured vision-capable model."
                )
        except Exception:  # noqa: BLE001
            fmt, width, height = IdeaAttachments._fallback_image_dimensions(content)
            return (
                "Image file analysis: "
                f"format={fmt}; width_px={width or 'unknown'}; height_px={height or 'unknown'}. "
                "Semantic content, screenshots and OCR require a configured vision-capable model."
            )

    @staticmethod
    def _path_category(path: str) -> str:
        lower = path.lower()
        suffix = Path(lower).suffix
        if suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".cs", ".c", ".h", ".hpp", ".cpp", ".swift", ".php", ".rb", ".sh", ".ps1", ".sql", ".html", ".css", ".scss"}:
            return "source_code"
        if suffix in {".json", ".yaml", ".yml", ".toml", ".ini", ".env", ".xml", ".cfg", ".conf"} or lower.endswith(("dockerfile", "makefile", "requirements.txt", "package.json", "pyproject.toml")):
            return "configuration"
        if suffix in {".md", ".txt", ".rst", ".adoc"}:
            return "text_document"
        if suffix == ".pdf":
            return "pdf_document"
        if suffix in {".docx", ".doc"}:
            return "word_document"
        if suffix in {".xlsx", ".xls", ".csv", ".tsv"}:
            return "spreadsheet"
        if suffix in {".pptx", ".ppt"}:
            return "presentation"
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}:
            return "image"
        if suffix in {".zip", ".7z", ".rar", ".tar", ".gz"}:
            return "nested_archive"
        if suffix in {".bin", ".elf", ".uf2", ".fw", ".firmware", ".hex", ".ino"}:
            return "firmware_or_device"
        return "binary_or_other"

    @staticmethod
    def _decode_text(filename: str, file_type: str, content: bytes) -> tuple[str, str]:
        name = (filename or "").lower()
        ctype = (file_type or "").lower()
        if name.endswith(".docx") or "wordprocessingml" in ctype:
            return IdeaAttachments._extract_docx_text(content), "docx_document"
        if name.endswith(".pptx") or "presentationml" in ctype:
            return IdeaAttachments._extract_pptx_text(content), "pptx_presentation"
        if name.endswith(".xlsx") or "spreadsheetml" in ctype:
            return IdeaAttachments._extract_xlsx_text(content), "xlsx_workbook"
        if name.endswith(".pdf") or "pdf" in ctype:
            return IdeaAttachments._extract_pdf_text(content), "pdf_document"
        if name.endswith((".doc", ".xls", ".ppt")) or ctype in {
            "application/msword",
            "application/vnd.ms-excel",
            "application/vnd.ms-powerpoint",
        }:
            return (
                "Legacy Office binary analysis: "
                f"filename={filename}; size_bytes={len(content)}; sha256={hashlib.sha256(content).hexdigest()}. "
                "Detailed text extraction requires a legacy Office converter or OCR/vision pipeline."
            ), "legacy_office_document"
        if name.endswith(".zip") or "zip" in ctype:
            extracted = IdeaAttachments._summarize_zip_archive(content)
            if extracted:
                return extracted, "zip_archive"
        text_like = (
            ctype.startswith("text/")
            or "json" in ctype
            or "xml" in ctype
            or name.endswith((
                ".txt", ".md", ".rst", ".rtf", ".svg", ".json", ".yaml", ".yml", ".toml",
                ".ini", ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
                ".html", ".css", ".scss", ".sql", ".go", ".rs", ".java", ".kt",
                ".cs", ".php", ".rb", ".sh", ".ps1", ".ino", ".c", ".h",
                ".hpp", ".cpp", ".hex",
            ))
        )
        if not text_like:
            if ctype.startswith("image/"):
                return IdeaAttachments._summarize_image(content), "image_binary"
            if name.endswith((".bin", ".elf", ".uf2", ".fw", ".firmware")):
                return "", "firmware_binary"
            return "", "binary"
        text = content.decode("utf-8", errors="replace")
        if name.endswith(".svg") or "svg" in ctype:
            text = re.sub(r"<[^>]+>", " ", text)
            text = IdeaAttachments._normalize_preview_text(text, limit=20000)
            return f"SVG diagram text: {text}", "svg_diagram"
        normalized = IdeaAttachments._normalize_preview_text(text, preserve_lines=True, limit=22000)
        if IdeaAttachments._path_category(filename) in {"source_code", "configuration", "firmware_or_device"}:
            return (
                f"Source/config file analysis: filename={filename}; size_bytes={len(content)}.\n"
                f"{normalized}"
            ), "source_code"
        return (
            f"Text document analysis: filename={filename}; size_bytes={len(content)}.\n"
            f"{normalized}"
        ), "text_document"

    @staticmethod
    def _zip_member_is_text(path: str) -> bool:
        lower = path.lower()
        return lower.endswith((
            ".txt", ".md", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini",
            ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".html",
            ".css", ".scss", ".sql", ".sh", ".ps1", ".bat", ".cmd", ".xml",
            ".go", ".rs", ".java", ".kt", ".cs", ".php", ".rb",
            ".svg", ".csv", ".env.example", ".gitignore", ".dockerfile",
            "dockerfile", "makefile", "requirements.txt", "pyproject.toml",
            "package.json", "pnpm-lock.yaml", "package-lock.json",
            "readme", "readme.md",
        ))

    @staticmethod
    def _safe_zip_path(path: str) -> bool:
        normalized = path.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        if normalized.startswith("/") or normalized.startswith("../"):
            return False
        if any(part == ".." for part in parts):
            return False
        if parts and re.match(r"^[A-Za-z]:$", parts[0]):
            return False
        return True

    @staticmethod
    def _zip_member_preview(filename: str, raw: bytes, category: str) -> str:
        lower = filename.lower()
        if category == "nested_archive":
            return "Nested archive detected; nested archive content is not expanded inside this digest."
        if lower.endswith(".docx"):
            return IdeaAttachments._extract_docx_text(raw)
        if lower.endswith(".pptx"):
            return IdeaAttachments._extract_pptx_text(raw)
        if lower.endswith(".xlsx"):
            return IdeaAttachments._extract_xlsx_text(raw)
        if lower.endswith(".pdf"):
            return IdeaAttachments._extract_pdf_text(raw)
        if category == "image":
            return IdeaAttachments._summarize_image(raw)
        if IdeaAttachments._zip_member_is_text(filename) or category in {"source_code", "configuration", "text_document", "spreadsheet"}:
            decoded = raw.decode("utf-8", errors="replace")
            return IdeaAttachments._normalize_preview_text(decoded, preserve_lines=True, limit=5000)
        return ""

    @staticmethod
    def _zip_path_parts(path: str) -> list[str]:
        return [
            part.lower()
            for part in path.replace("\\", "/").split("/")
            if part and part not in {".", ".."}
        ]

    @staticmethod
    def _zip_member_is_dependency_or_generated(path: str) -> bool:
        parts = IdeaAttachments._zip_path_parts(path)
        if any(part in {
            "node_modules",
            ".git",
            ".next",
            ".nuxt",
            ".turbo",
            ".vite",
            "dist",
            "build",
            "coverage",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "vendor",
        } for part in parts):
            return True
        lower = path.lower()
        return lower.endswith((".map", ".min.js", ".min.css", ".lockb"))

    @staticmethod
    def _zip_member_priority(item: zipfile.ZipInfo) -> tuple[int, int, str]:
        name = item.filename.replace("\\", "/")
        lower = name.lower()
        category = IdeaAttachments._path_category(name)
        score = 90 if IdeaAttachments._zip_member_is_dependency_or_generated(name) else 0

        if category in {"source_code", "configuration"}:
            score += 0
        elif category in {"text_document", "pdf_document", "word_document", "spreadsheet", "presentation"}:
            score += 8
        elif category == "image":
            score += 18
        else:
            score += 35

        if any(token in lower for token in (
            "readme",
            "architecture",
            "adr/",
            "docs/",
            "openapi",
            "schema",
            "package.json",
            "pyproject.toml",
            "docker-compose",
            "dockerfile",
            "terraform",
            "ansible",
            "src/",
            "app/",
            "pages/",
            "components/",
            "api/",
            "tests/",
            "e2e/",
        )):
            score -= 15
        if lower.endswith((".lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock")):
            score += 22
        return (score, -min(int(item.file_size or 0), 50_000), lower)

    @staticmethod
    def _zip_sample_paths(items: list[zipfile.ZipInfo], limit: int = 8) -> str:
        samples = [item.filename for item in items[:limit]]
        return "; ".join(samples) if samples else "none"

    @staticmethod
    def _zip_read_member_text(
        archive: zipfile.ZipFile,
        item: zipfile.ZipInfo,
        *,
        limit: int = 20000,
    ) -> str:
        try:
            if item.file_size > limit:
                return ""
            with archive.open(item, "r") as member:
                return member.read(min(int(item.file_size or 0), limit)).decode("utf-8", errors="replace")
        except (OSError, RuntimeError, zipfile.BadZipFile, NotImplementedError, KeyError):
            return ""

    @staticmethod
    def _zip_parent_dir(path: str) -> str:
        normalized = path.replace("\\", "/").strip("/")
        if "/" not in normalized:
            return "."
        return normalized.rsplit("/", 1)[0] or "."

    @staticmethod
    def _zip_deploy_test_readiness(files: list[zipfile.ZipInfo], archive: zipfile.ZipFile) -> list[str]:
        relevant = [
            item for item in files
            if (
                IdeaAttachments._safe_zip_path(item.filename)
                and not IdeaAttachments._zip_member_is_dependency_or_generated(item.filename)
            )
        ]
        path_by_item = {item: item.filename.replace("\\", "/") for item in relevant}
        lower_by_item = {item: path.lower() for item, path in path_by_item.items()}
        package_files = [item for item, path in lower_by_item.items() if path.endswith("package.json")]
        pyproject_files = [item for item, path in lower_by_item.items() if path.endswith("pyproject.toml")]
        requirements_files = [item for item, path in lower_by_item.items() if path.endswith("requirements.txt")]
        dockerfiles = [item for item, path in lower_by_item.items() if path.endswith("dockerfile") or "/dockerfile" in path]
        compose_files = [
            item for item, path in lower_by_item.items()
            if "docker-compose" in path and path.endswith((".yml", ".yaml"))
        ]
        workflow_files = [item for item, path in lower_by_item.items() if ".github/workflows/" in path]
        env_templates = [
            item for item, path in lower_by_item.items()
            if path.endswith((".env.example", ".env.sample", ".env.template"))
        ]
        test_files = [
            item for item, path in lower_by_item.items()
            if "test" in path or "spec." in path or "e2e/" in path
        ]

        script_summaries: list[str] = []
        package_roots: list[str] = []
        install_hints: list[str] = []
        run_hints: list[str] = []
        test_hints: list[str] = []
        for item in package_files[:12]:
            root = IdeaAttachments._zip_parent_dir(path_by_item[item])
            package_roots.append(root)
            raw = IdeaAttachments._zip_read_member_text(archive, item, limit=50000)
            try:
                parsed = json.loads(raw or "{}")
            except json.JSONDecodeError:
                script_summaries.append(f"{path_by_item[item]} -> package.json parse error")
                continue
            scripts = parsed.get("scripts") if isinstance(parsed, dict) else {}
            deps = parsed.get("dependencies") if isinstance(parsed, dict) else {}
            dev_deps = parsed.get("devDependencies") if isinstance(parsed, dict) else {}
            script_names = sorted(scripts) if isinstance(scripts, dict) else []
            dep_names = sorted(list(deps)[:8]) if isinstance(deps, dict) else []
            dev_dep_names = sorted(list(dev_deps)[:8]) if isinstance(dev_deps, dict) else []
            script_summaries.append(
                f"{path_by_item[item]} -> scripts={', '.join(script_names[:12]) or 'none'}; "
                f"deps={', '.join(dep_names) or 'none'}; devDeps={', '.join(dev_dep_names) or 'none'}"
            )
            if "pnpm-lock.yaml" in "\n".join(lower_by_item.values()):
                install_hints.append(f"cd {root} && pnpm install --frozen-lockfile")
            elif "yarn.lock" in "\n".join(lower_by_item.values()):
                install_hints.append(f"cd {root} && yarn install --frozen-lockfile")
            elif "package-lock.json" in "\n".join(lower_by_item.values()):
                install_hints.append(f"cd {root} && npm ci")
            else:
                install_hints.append(f"cd {root} && npm install")
            for name in ("dev", "start", "preview"):
                if name in script_names:
                    run_hints.append(f"cd {root} && npm run {name}")
            for name in ("test", "test:e2e", "e2e", "lint", "typecheck", "build"):
                if name in script_names:
                    test_hints.append(f"cd {root} && npm run {name}")

        python_roots = [IdeaAttachments._zip_parent_dir(path_by_item[item]) for item in pyproject_files + requirements_files]
        for root in python_roots[:8]:
            install_hints.append(f"cd {root} && python -m pip install -r requirements.txt OR python -m pip install -e .")
            test_hints.append(f"cd {root} && python -m pytest")

        blockers: list[str] = []
        if not package_files and not pyproject_files and not requirements_files and not compose_files:
            blockers.append("No package.json, pyproject.toml, requirements.txt or docker-compose file detected outside generated/dependency folders.")
        if not env_templates:
            blockers.append("No .env.example/.env.sample detected; runtime secrets/config may be unknown.")
        if not test_files:
            blockers.append("No obvious test/spec/e2e files detected in safe project paths.")
        if not dockerfiles and not compose_files:
            blockers.append("No Dockerfile/docker-compose detected; sandbox deploy needs inferred local commands.")
        if any(IdeaAttachments._zip_member_is_dependency_or_generated(item.filename) for item in files):
            blockers.append("Archive contains dependency/generated folders; sandbox should ignore them and install dependencies fresh inside an isolated workspace.")

        lines = [
            "Sandbox deploy and test readiness:",
            (
                "No uploaded code is executed during attachment analysis. Actual install/build/test/deploy must run only "
                "inside an isolated sandbox after explicit operator/HumanGate approval."
            ),
            f"Candidate app roots: {', '.join(sorted(set(package_roots + python_roots))[:12]) or 'none'}",
            f"Node/package manifests: {len(package_files)}; Python manifests: {len(pyproject_files) + len(requirements_files)}; Dockerfiles: {len(dockerfiles)}; compose files: {len(compose_files)}; CI workflows: {len(workflow_files)}; env templates: {len(env_templates)}; test files: {len(test_files)}.",
            "Package/script evidence: " + (" | ".join(script_summaries[:10]) if script_summaries else "none"),
            "Suggested sandbox install commands: " + (" | ".join(dict.fromkeys(install_hints)) if install_hints else "none inferred"),
            "Suggested sandbox run commands: " + (" | ".join(dict.fromkeys(run_hints)) if run_hints else "none inferred"),
            "Suggested sandbox validation commands: " + (" | ".join(dict.fromkeys(test_hints)) if test_hints else "none inferred"),
            "Docker/CI evidence: "
            + (
                f"docker={IdeaAttachments._zip_sample_paths(dockerfiles + compose_files, 10)}; "
                f"ci={IdeaAttachments._zip_sample_paths(workflow_files, 10)}"
            ),
            "Runtime blockers before automatic deploy: " + (" | ".join(blockers) if blockers else "none obvious from static archive inspection"),
            (
                "If sandbox execution fails, AEIS should capture install/build/test logs, classify missing dependencies, "
                "missing env, port conflicts, failing tests, migrations, external services and browser-render failures."
            ),
        ]
        return lines

    @staticmethod
    def _zip_project_overview(files: list[zipfile.ZipInfo]) -> list[str]:
        relevant = [
            item for item in files
            if (
                IdeaAttachments._safe_zip_path(item.filename)
                and not IdeaAttachments._zip_member_is_dependency_or_generated(item.filename)
            )
        ]
        paths = [item.filename.replace("\\", "/") for item in relevant]
        lowered = [path.lower() for path in paths]
        root_dirs = Counter(path.split("/")[0] for path in paths if "/" in path)
        doc_files = [
            item for item in relevant
            if any(token in item.filename.replace("\\", "/").lower() for token in (
                "readme", "docs/", "adr/", "runbook", "architecture", "openapi", "swagger",
                "summary", "feature", "requirements",
            ))
        ]
        entry_files = [
            item for item in relevant
            if item.filename.replace("\\", "/").lower().endswith((
                "package.json", "pyproject.toml", "docker-compose.yml", "docker-compose.yaml",
                "dockerfile", "main.ts", "main.tsx", "app.ts", "server.ts", "index.ts",
                "index.tsx", "openapi.yaml", "openapi.yml", "openapi.json",
            ))
        ]
        deployment_files = [
            item for item in relevant
            if any(token in item.filename.replace("\\", "/").lower() for token in (
                "deploy/", "docker", "terraform", "ansible", "nginx", "caddy",
                ".github/workflows", "helm", "k8s", "kubernetes",
            ))
        ]

        domain_signals: list[tuple[str, tuple[str, ...], str]] = [
            ("tailoring / fashion production", ("tailor", "pattern", "measurement", "garment", "fabric", "sizing"), "system wspiera szycie, wzorce, miary, materiały i obsługę produkcji krawieckiej"),
            ("CRM / customer operations", ("crm", "customer", "client", "order", "appointment", "invoice"), "system obsługuje klientów, zamówienia, spotkania lub sprzedaż"),
            ("discovery / inspiration intake", ("discovery", "inspiration", "trend", "source_url", "scrape"), "system pobiera albo porządkuje inspiracje i trendy z zewnętrznych źródeł"),
            ("inventory / production operations", ("inventory", "stock", "warehouse", "reorder", "waste", "production"), "system ma warstwę magazynu, zapasów lub operacji produkcyjnych"),
            ("AI assistance / optimisation", ("ai/", "llm", "prompt", "optimize", "recommend", "model"), "system używa modeli lub heurystyk do rekomendacji, optymalizacji albo analizy"),
            ("mobile / offline workflow", ("mobile", "offline", "sync", "pwa", "device"), "system ma ścieżkę mobilną, offline albo synchronizację terenową"),
            ("funding / grant workflow", ("funding", "grant", "horizon", "trl", "application"), "system zawiera elementy finansowania, grantów albo dokumentacji konkursowej"),
        ]
        detected_domains = [
            f"{label} -> {meaning}"
            for label, tokens, meaning in domain_signals
            if any(any(token in path for token in tokens) for path in lowered)
        ]

        lines = [
            "Project purpose and operating model:",
            (
                "Likely purpose is inferred from documentation, module names, routes and tests; "
                "treat it as evidence-guided until full source review confirms behaviour."
            ),
        ]
        if detected_domains:
            lines.append("Likely product purpose: " + "; ".join(detected_domains[:6]) + ".")
        else:
            lines.append("Likely product purpose: not enough domain-specific path evidence in bounded digest.")
        if root_dirs:
            lines.append("Repository layout: " + ", ".join(f"{name}:{count}" for name, count in root_dirs.most_common(8)))
        lines.append(
            "Documentation evidence: "
            f"{len(doc_files)} candidate docs; examples={IdeaAttachments._zip_sample_paths(doc_files, 12)}"
        )
        lines.append(
            "Entrypoints and configuration evidence: "
            f"{len(entry_files)} candidate files; examples={IdeaAttachments._zip_sample_paths(entry_files, 12)}"
        )
        lines.append(
            "Deployment/operations evidence: "
            f"{len(deployment_files)} candidate files; examples={IdeaAttachments._zip_sample_paths(deployment_files, 12)}"
        )
        lines.append(
            "How it appears to work: operator/user uses frontend routes and components; those call API/backend modules; "
            "domain services cover tailoring/customer/discovery/production signals when present; tests and deployment files indicate validation and release paths."
        )
        lines.append(
            "Full-review requirement: verify README/docs first, then package scripts and OpenAPI, then UI route flows, "
            "then API handlers/services, then tests and deployment. Do not accept a model answer that skips these layers."
        )
        return lines

    @staticmethod
    def _zip_functionality_inventory(files: list[zipfile.ZipInfo]) -> list[str]:
        relevant = [
            item for item in files
            if (
                IdeaAttachments._safe_zip_path(item.filename)
                and not IdeaAttachments._zip_member_is_dependency_or_generated(item.filename)
            )
        ]
        lowered = [(item, item.filename.replace("\\", "/").lower()) for item in relevant]
        rules: list[tuple[str, tuple[str, ...]]] = [
            ("UI / frontend screens and components", ("app/", "pages/", "components/", "client/src", ".tsx", ".jsx")),
            ("API and backend routing", ("/api/", "routes", "controller", "server", "openapi", "swagger")),
            ("Authentication, identity and permissions", ("auth", "login", "jwt", "session", "rbac", "permission", "tenant")),
            ("CRM, customers and orders", ("crm", "customer", "client", "order", "invoice", "appointment")),
            ("Fashion/tailoring domain", ("tailor", "pattern", "measurement", "garment", "fabric", "material", "sizing")),
            ("Inventory and operations", ("inventory", "stock", "warehouse", "reorder", "waste", "production")),
            ("Discovery, inspirations and trend intake", ("discovery", "inspiration", "trend", "source_url", "scrape")),
            ("AI optimisation or model-assisted work", ("ai/", "llm", "prompt", "optimize", "recommend", "model")),
            ("Mobile and offline workflow", ("mobile", "offline", "sync", "pwa", "device")),
            ("Alerts, monitoring and health", ("alert", "monitor", "metric", "health", "observability", "log")),
            ("Funding, grants and external sources", ("funding", "grant", "horizon", "trl", "application")),
            ("Security, privacy and compliance", ("security", "privacy", "gdpr", "pii", "audit", "policy", "retention")),
            ("Deployment and infrastructure", ("deploy/", "docker", "terraform", "ansible", "nginx", "caddy", ".github/workflows")),
            ("Automated tests and QA", ("test", "spec.", "e2e/", "playwright", "vitest", "pytest")),
            ("Documentation and architecture evidence", ("docs/", "adr/", "readme", "runbook", "architecture")),
        ]

        lines = [
            "Functional capability map:",
            (
                "This map is inferred from archive paths and selected readable previews. "
                "It identifies what the project appears to contain; each item still needs code/test verification."
            ),
        ]
        for label, tokens in rules:
            matches = [
                item for item, path in lowered
                if any(token in path for token in tokens)
            ]
            if not matches:
                continue
            category_counts = Counter(IdeaAttachments._path_category(item.filename) for item in matches)
            category_summary = ", ".join(
                f"{name}:{count}" for name, count in category_counts.most_common(4)
            )
            lines.append(
                f"- {label}: {len(matches)} files; categories={category_summary or 'n/a'}; "
                f"evidence={IdeaAttachments._zip_sample_paths(matches)}"
            )

        domain_counter: Counter[str] = Counter()
        route_counter: Counter[str] = Counter()
        for _, path in lowered:
            parts = [part for part in path.split("/") if part]
            for marker in ("src/domain", "src/api", "src/engine", "src/ai", "src/mobile", "src/alerts"):
                marker_parts = marker.split("/")
                for index in range(0, max(0, len(parts) - len(marker_parts)) + 1):
                    if parts[index:index + len(marker_parts)] == marker_parts and index + len(marker_parts) < len(parts):
                        domain_counter[f"{marker}/{parts[index + len(marker_parts)]}"] += 1
            if "app" in parts:
                app_index = parts.index("app")
                if app_index + 1 < len(parts):
                    route_counter[f"app/{parts[app_index + 1]}"] += 1
            if "pages" in parts:
                pages_index = parts.index("pages")
                if pages_index + 1 < len(parts):
                    route_counter[f"pages/{parts[pages_index + 1]}"] += 1

        if domain_counter:
            lines.append(
                "Domain/module clusters: "
                + ", ".join(f"{name}:{count}" for name, count in domain_counter.most_common(14))
            )
        if route_counter:
            lines.append(
                "Likely UI route clusters: "
                + ", ".join(f"{name}:{count}" for name, count in route_counter.most_common(14))
            )

        test_files = [item for item, path in lowered if "test" in path or "spec." in path or "e2e/" in path]
        if test_files:
            lines.append(
                "Functional test evidence: "
                f"{len(test_files)} candidate test files; evidence={IdeaAttachments._zip_sample_paths(test_files, 10)}"
            )
        if not any(line.startswith("- ") for line in lines):
            lines.append("- No clear functional modules inferred from safe non-generated paths.")
        return lines

    @staticmethod
    def _summarize_zip_archive(content: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                files = [item for item in entries if not item.is_dir()]
                dirs = [item for item in entries if item.is_dir()]
                unsafe_paths = [item.filename for item in entries if not IdeaAttachments._safe_zip_path(item.filename)]
                symlinks = [
                    item.filename
                    for item in entries
                    if ((item.external_attr >> 16) & 0o170000) == 0o120000
                ]
                total_uncompressed = sum(max(0, int(item.file_size or 0)) for item in files)
                total_compressed = sum(max(0, int(item.compress_size or 0)) for item in files)
                compression_ratio = (
                    round(total_uncompressed / max(1, total_compressed), 2)
                    if total_uncompressed
                    else 0
                )
                ext_counter = Counter(
                    (Path(item.filename).suffix.lower() or "[no_ext]")
                    for item in files
                )
                category_counter = Counter(
                    IdeaAttachments._path_category(item.filename)
                    for item in files
                )
                top_dirs = Counter(
                    item.filename.replace("\\", "/").split("/")[0]
                    for item in files
                    if "/" in item.filename.replace("\\", "/")
                )
                overview_lines = IdeaAttachments._zip_project_overview(files)
                functionality_lines = IdeaAttachments._zip_functionality_inventory(files)
                deploy_readiness_lines = IdeaAttachments._zip_deploy_test_readiness(files, archive)
                prioritized_files = sorted(files, key=IdeaAttachments._zip_member_priority)
                dependency_files = [
                    item for item in files
                    if IdeaAttachments._zip_member_is_dependency_or_generated(item.filename)
                ]
                manifest_files = prioritized_files
                manifest_lines = [
                    f"- {item.filename} | {IdeaAttachments._path_category(item.filename)} | {item.file_size} bytes"
                    for item in manifest_files[:220]
                ]
                previews: list[str] = []
                content_budget = 120000
                preview_limit = 90
                skipped_large = 0
                skipped_unsupported = 0
                skipped_dependency = 0
                for item in prioritized_files:
                    if len(previews) >= preview_limit or content_budget <= 0:
                        break
                    if not IdeaAttachments._safe_zip_path(item.filename):
                        continue
                    if IdeaAttachments._zip_member_is_dependency_or_generated(item.filename):
                        skipped_dependency += 1
                        continue
                    category = IdeaAttachments._path_category(item.filename)
                    previewable = (
                        category in {
                            "source_code",
                            "configuration",
                            "text_document",
                            "pdf_document",
                            "word_document",
                            "spreadsheet",
                            "presentation",
                            "image",
                            "nested_archive",
                            "firmware_or_device",
                        }
                        or IdeaAttachments._zip_member_is_text(item.filename)
                    )
                    if not previewable:
                        skipped_unsupported += 1
                        continue
                    if item.file_size > 8_000_000:
                        skipped_large += 1
                        previews.append(
                            f"### {item.filename} ({category}, {item.file_size} bytes)\n"
                            "File is above the per-file preview limit; metadata included in manifest."
                        )
                        continue
                    try:
                        with archive.open(item, "r") as member:
                            raw = member.read(min(int(item.file_size or 0), 8_000_000, content_budget))
                    except (OSError, RuntimeError, zipfile.BadZipFile, NotImplementedError):
                        continue
                    if category == "firmware_or_device" and not IdeaAttachments._zip_member_is_text(item.filename):
                        preview = (
                            f"Firmware/device file metadata: size_bytes={item.file_size}; "
                            f"sha256={hashlib.sha256(raw).hexdigest()}."
                        )
                    else:
                        preview = IdeaAttachments._zip_member_preview(item.filename, raw, category)
                    preview = IdeaAttachments._normalize_preview_text(preview, preserve_lines=True, limit=5000)
                    if not preview:
                        skipped_unsupported += 1
                        continue
                    previews.append(f"### {item.filename} ({category}, {item.file_size} bytes)\n{preview}")
                    content_budget -= len(preview)

                lines = [
                    f"ZIP archive detailed analysis: entries={len(entries)}; files={len(files)}; directories={len(dirs)}; "
                    f"compressed_bytes={len(content)}; uncompressed_bytes={total_uncompressed}; "
                    f"compression_ratio={compression_ratio}.",
                    "Analysis coverage: metadata_all_files=true; "
                    f"manifest_rows={min(len(manifest_lines), len(files))}/{len(files)}; "
                    f"content_previews={len(previews)}/{len(files)}; per_file_preview_limit_bytes=8000000; "
                    f"digest_budget_chars=120000; skipped_large={skipped_large}; "
                    f"skipped_unsupported={skipped_unsupported}; skipped_dependency_or_generated={len(dependency_files)}.",
                    "Top extensions: " + (
                        ", ".join(f"{ext}:{count}" for ext, count in ext_counter.most_common(12))
                        or "none"
                    ),
                    "File categories: " + (
                        ", ".join(f"{name}:{count}" for name, count in category_counter.most_common(12))
                        or "none"
                    ),
                    "Top directories: " + (
                        ", ".join(f"{name}:{count}" for name, count in top_dirs.most_common(10))
                        or "root-only"
                    ),
                ]
                lines.extend(overview_lines)
                lines.extend(functionality_lines)
                lines.extend(deploy_readiness_lines)
                if unsafe_paths:
                    lines.append("Unsafe paths detected: " + "; ".join(unsafe_paths[:10]))
                if symlinks:
                    lines.append("Symlinks detected: " + "; ".join(symlinks[:10]))
                if previews:
                    lines.append("Detailed content previews:")
                    lines.extend(previews)
                else:
                    lines.append("Detailed content previews: none readable; archive may contain only unsupported binary files.")
                if dependency_files:
                    lines.append(
                        "Dependency/generated files skipped from content previews: "
                        f"{len(dependency_files)} total; {skipped_dependency} reached after priority sorting; "
                        "they remain covered by metadata and extension counts."
                    )
                if manifest_lines:
                    lines.append("Detailed manifest:")
                    lines.extend(manifest_lines)
                    if len(files) > len(manifest_lines):
                        lines.append(f"- ... {len(files) - len(manifest_lines)} additional files omitted from manifest preview.")
                return "\n".join(lines)
        except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
            return f"ZIP archive could not be opened safely: {type(exc).__name__}: {str(exc)[:180]}"

    @staticmethod
    def _contains_any(text: str, needles: list[str]) -> bool:
        return any(needle in text for needle in needles)

    def _derive_analysis(self, filename: str, file_type: str, content: bytes) -> dict:
        extracted, detected_kind = self._decode_text(filename, file_type, content)
        name = (filename or "").lower()
        lowered = extracted.lower()
        tags: list[str] = []
        risks: list[str] = []
        missing: list[str] = []
        skills: list[str] = ["idea_attachment_reader"]
        decision_class = "D1"
        image_status = "not_applicable"
        is_firmware = detected_kind == "firmware_binary" or name.endswith((".ino", ".bin", ".hex", ".elf", ".uf2", ".fw", ".firmware"))
        firmware_hash = hashlib.sha256(content).hexdigest() if is_firmware else ""

        if detected_kind == "image_binary":
            tags.extend(["image_attachment", "vision_required"])
            image_status = "requires_vision_model"
            missing.append("Image content requires a configured vision-capable model.")
            skills.append("vision_attachment_analyzer")
            decision_class = "D2"
        elif detected_kind == "zip_archive":
            tags.extend(["zip_archive", "attachment_inventory", "deep_attachment_digest"])
            skills.extend(["zip_attachment_analyzer", "codebase_inventory_reader"])
            if self._contains_any(lowered, ["source_code", "package.json", "pyproject.toml", "dockerfile", "requirements.txt"]):
                tags.extend(["software_project", "codebase"])
                skills.extend(["codebase_auditor", "dependency_risk_reviewer"])
            if self._contains_any(lowered, ["pdf_document", "word_document", "spreadsheet", "presentation"]):
                skills.extend(["document_content_reviewer", "source_citation_checker"])
            if self._contains_any(lowered, ["image", "vision-capable"]):
                skills.append("vision_attachment_analyzer")
            if self._contains_any(lowered, ["unsafe paths detected", "symlinks detected"]):
                risks.append("ZIP archive contains unsafe paths or symlinks and requires HumanGate review.")
            if self._contains_any(lowered, ["additional files omitted", "above the per-file preview limit", "content_previews=0/"]):
                missing.append("Archive has files whose full content is not represented in the bounded council digest.")
            if self._contains_any(lowered, ["unsafe paths detected", "symlinks detected"]):
                decision_class = "D3"
            else:
                decision_class = "D2"
        elif detected_kind == "pdf_document":
            tags.append("pdf_attachment")
            skills.extend(["pdf_text_extractor", "document_content_reviewer"])
            if self._contains_any(lowered, ["no extractable text", "ocr", "parser_error"]):
                missing.append("PDF requires OCR or parser repair before the Council can inspect scanned/hidden text.")
                skills.append("vision_attachment_analyzer")
            decision_class = "D2"
        elif detected_kind in {"docx_document", "pptx_presentation", "xlsx_workbook"}:
            tags.extend(["office_document", detected_kind])
            skills.extend(["document_content_reviewer", "source_citation_checker"])
            decision_class = "D2"
        elif detected_kind == "legacy_office_document":
            tags.extend(["office_document", "legacy_binary_document"])
            missing.append("Legacy DOC/XLS/PPT needs a converter or OCR/vision pipeline before full Council review.")
            skills.extend(["document_content_reviewer", "legacy_office_converter"])
            decision_class = "D2"
        elif detected_kind == "source_code":
            tags.extend(["source_code", "implementation_material"])
            skills.extend(["codebase_auditor", "dependency_risk_reviewer"])
            decision_class = "D2"
        elif detected_kind == "text_document":
            tags.append("text_attachment")
        elif detected_kind == "firmware_binary":
            extracted = (
                f"Firmware binary metadata: filename={filename}; "
                f"size_bytes={len(content)}; sha256={firmware_hash}; "
                "requires firmware_attachment_guard and secure_approval before sync."
            )
            lowered = extracted.lower()
        elif detected_kind == "svg_diagram":
            skills.append("svg_context_extractor")

        mental_health_tokens = [
            "mental",
            "wellbeing",
            "psych",
            "psychoeduk",
            "nastroj",
            "nastrój",
            "samoboj",
            "samobój",
            "autoagres",
            "kryzys",
            "terapi",
            "diagnoz",
            "porad medycz",
            "emergency hand-off",
            "safety classifier",
        ]
        is_mental_health = self._contains_any(lowered, mental_health_tokens)
        if is_mental_health:
            tags.extend(["mental_health", "safety_critical", "human_gate_expected"])
            skills.extend([
                "mental_health_safety_classifier",
                "crisis_response_guard",
                "no_medical_advice_guard",
                "privacy_risk_reviewer",
                "source_citation_checker",
            ])
            risks.append("Mental-health or wellbeing attachment requires crisis-safe responses and no medical diagnosis or therapy advice.")
            risks.append("Publication, external model use and emergency resource changes require HumanGate.")
            decision_class = "D5"

        if is_firmware:
            tags.extend(["firmware", "device_update", "security", "human_gate_expected"])
            skills.extend(["firmware_attachment_guard", "device_binding", "secure_approval", "audit_evidence_pack"])
            risks.append("Firmware attachment can change field device behavior and requires hash evidence.")
            risks.append(f"Firmware sha256 proof: {firmware_hash}")
            decision_class = "D4"

        if self._contains_any(lowered, ["pii", "gdpr", "dane osob", "hr", "retenc", "anonimiz", "redakc"]):
            tags.extend(["pii_scope", "gdpr", "security"])
            skills.extend(["pii_redactor", "gdpr_dsr", "retention_policy_checker"])
            risks.append("Attachment describes personal-data processing.")
            decision_class = "D4"
        if self._contains_any(lowered, ["medycz", "healthcare", "wynagrodz", "documentow hr", "umow"]):
            risks.append("Potential sensitive HR/medical/legal data may require stricter handling.")
            decision_class = "D4"
        if self._contains_any(lowered, [" d5", "d5,", "d5.", "genom", "genomic", "pacjent", "klinicz", "clinical"]):
            tags.extend(["health_research", "sensitive_research", "human_gate_expected"])
            if self._contains_any(lowered, ["genom", "genomic", "fastq", "vcf", "wariant", "variant", "pacjent"]):
                skills.extend(["bioinformatics_guard", "clinical_safety_disclaimer", "privacy_risk_reviewer"])
                risks.append("Genomic/clinical-context attachment must be treated as D5 even when data is synthetic.")
            elif not is_mental_health:
                skills.extend(["clinical_safety_disclaimer", "privacy_risk_reviewer"])
                risks.append("Clinical-context attachment must be treated as D5.")
            risks.append("Clinical or patient-facing interpretation is prohibited without explicit human governance.")
            decision_class = "D5"
        if self._contains_any(lowered, ["grant", "horizon", "feng", "smart", "eic", "digital europe", "ncbr", "parp"]):
            tags.extend(["funding", "external_sources"])
            skills.extend(["funding_research", "grant_deadline_verifier", "source_citation_checker"])
            risks.append("Grant deadlines and eligibility must be source-backed and current.")
            decision_class = max(decision_class, "D3")
        if self._contains_any(lowered, ["kwant", "quantum", "kryptograf", "post-kwant", "cyberbezpiec", "nis2"]):
            tags.extend(["deep_tech", "cybersecurity"])
            skills.append("deeptech_domain_reviewer")
        if self._contains_any(lowered, ["upload", "plik", "pdf", "docx"]):
            skills.append("file_upload_validator")
        if self._contains_any(lowered, ["human gate", "humangate", "hg", "d4"]):
            tags.append("human_gate_expected")

        if "retenc" not in lowered and "retention" not in lowered and "pii" in tags:
            missing.append("Retention policy for original documents is missing.")
        if "external llm" in lowered or "model llm" in lowered or "zewnetrzn" in lowered:
            risks.append("External LLM processing policy must be explicitly approved.")
        elif "pii" in tags:
            missing.append("External LLM/data residency policy is missing.")
        if "deadline" in lowered and "source" not in lowered and "zrod" not in lowered:
            missing.append("Deadlines require official source URLs.")
        if "trl" in lowered and "nie wiadomo" in lowered:
            missing.append("Project TRL must be supplied before grant matching.")
        if "budzet" in lowered and "nie podano" in lowered:
            missing.append("Project/application budget is missing.")

        if not extracted and detected_kind in {"binary", "image_binary", "pdf_document"}:
            risks.append("Specialized attachment analyzer required before canonical freeze.")

        tags = sorted(set(tags))
        skills = sorted(set(skills))
        human_gate_required = decision_class in {"D3", "D4", "D5"}
        return {
            "detected_kind": detected_kind,
            "extracted_text_preview": extracted[:60000],
            "tags": tags,
            "risks": risks,
            "missing_info": missing,
            "suggested_skills": skills,
            "decision_class": decision_class,
            "human_gate_required": human_gate_required,
            "image_analysis_status": image_status,
        }

    def analyze_attachment(self, attachment_id: str) -> dict:
        """Analyze one attachment and persist a replayable summary.

        The analysis is intentionally conservative: it extracts safe previews
        and operational metadata rather than copying full attachment content
        into audit-facing rows.
        """
        row = self._get_attachment_with_content(attachment_id)
        if not row:
            raise KeyError(f"attachment '{attachment_id}' not found")
        content = base64.b64decode(row["content_b64"])
        derived = self._derive_analysis(row["filename"], row["file_type"], content)
        analysis_id = self._uid()
        now = time.time()
        result = {
            "analysis_id": analysis_id,
            "attachment_id": row["attachment_id"],
            "idea_id": row["idea_id"],
            "filename": row["filename"],
            "file_type": row["file_type"],
            "file_size": row["file_size"],
            "content_sha256": hashlib.sha256(content).hexdigest(),
            **derived,
            "created_at": now,
        }
        with self._lock:
            self._conn.execute(
                "DELETE FROM idea_attachment_analysis WHERE attachment_id = ?",
                (row["attachment_id"],),
            )
            self._conn.execute(
                "INSERT INTO idea_attachment_analysis "
                "(analysis_id, attachment_id, idea_id, filename, file_type, "
                "file_size, content_sha256, detected_kind, extracted_text_preview, "
                "tags_json, risks_json, missing_info_json, suggested_skills_json, "
                "decision_class, human_gate_required, image_analysis_status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    analysis_id,
                    row["attachment_id"],
                    row["idea_id"],
                    row["filename"],
                    row["file_type"],
                    int(row["file_size"]),
                    result["content_sha256"],
                    result["detected_kind"],
                    result["extracted_text_preview"],
                    json.dumps(result["tags"], ensure_ascii=False),
                    json.dumps(result["risks"], ensure_ascii=False),
                    json.dumps(result["missing_info"], ensure_ascii=False),
                    json.dumps(result["suggested_skills"], ensure_ascii=False),
                    result["decision_class"],
                    1 if result["human_gate_required"] else 0,
                    result["image_analysis_status"],
                    now,
                ),
            )
            self._conn.commit()
        self._emit("attachment_analyzed", {
            "analysis_id": analysis_id,
            "attachment_id": row["attachment_id"],
            "idea_id": row["idea_id"],
            "filename": row["filename"],
            "decision_class": result["decision_class"],
            "human_gate_required": result["human_gate_required"],
            "tags": result["tags"],
        })
        return result

    @staticmethod
    def _analysis_row_to_dict(row: sqlite3.Row) -> dict:
        item = dict(row)
        for key in ("tags", "risks", "missing_info", "suggested_skills"):
            item[key] = json.loads(item.pop(f"{key}_json", "[]") or "[]")
        item["human_gate_required"] = bool(item.get("human_gate_required"))
        return item

    def list_attachment_analysis(self, idea_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT analysis_id, attachment_id, idea_id, filename, file_type, "
                "file_size, content_sha256, detected_kind, extracted_text_preview, "
                "tags_json, risks_json, missing_info_json, suggested_skills_json, "
                "decision_class, human_gate_required, image_analysis_status, created_at "
                "FROM idea_attachment_analysis WHERE idea_id = ? "
                "ORDER BY created_at DESC",
                (idea_id,),
            ).fetchall()
        latest: list[dict] = []
        seen: set[str] = set()
        for row in rows:
            item = self._analysis_row_to_dict(row)
            attachment_id = str(item.get("attachment_id") or "")
            if attachment_id in seen:
                continue
            seen.add(attachment_id)
            latest.append(item)
        return latest

    def analyze_idea_attachments(self, idea_id: str) -> list[dict]:
        return [
            self.analyze_attachment(item["attachment_id"])
            for item in self.list_attachments(idea_id)
        ]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_attachment_stats(self) -> dict:
        """Aggregate attachment statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM idea_attachments",
            ).fetchone()["cnt"]

            total_size = self._conn.execute(
                "SELECT COALESCE(SUM(file_size), 0) as total_size "
                "FROM idea_attachments",
            ).fetchone()["total_size"]

            type_rows = self._conn.execute(
                "SELECT file_type, COUNT(*) as cnt FROM idea_attachments "
                "GROUP BY file_type ORDER BY cnt DESC",
            ).fetchall()
            by_type = {r["file_type"]: r["cnt"] for r in type_rows}

            idea_rows = self._conn.execute(
                "SELECT idea_id, COUNT(*) as cnt FROM idea_attachments "
                "GROUP BY idea_id ORDER BY cnt DESC LIMIT 10",
            ).fetchall()
            by_idea = {r["idea_id"]: r["cnt"] for r in idea_rows}

        return {
            "total": total,
            "total_size": total_size,
            "by_type": by_type,
            "top_ideas": by_idea,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: IdeaAttachments | None = None


def get_idea_attachments(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> IdeaAttachments:
    global _instance
    if _instance is None:
        _instance = IdeaAttachments(db_path, event_bus)
    return _instance


def reset_idea_attachments(db_path: str | Path | None = None,
                           event_bus: EventBus | None = None) -> IdeaAttachments:
    global _instance
    _instance = IdeaAttachments(db_path, event_bus)
    return _instance
