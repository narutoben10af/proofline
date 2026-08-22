from __future__ import annotations

import hashlib
import hmac
import io
import logging
import os
import re
import secrets
import shutil
import stat
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from threading import Lock, RLock
from typing import Protocol
from xml.etree import ElementTree

from fastapi import UploadFile
from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

from proofline.contracts import (
    RemovalCount,
    SourceDeletionReceipt,
    SourceFileMetadata,
    SourceSessionCreated,
    SourceSessionStatus,
)

PDF_MIME = "application/pdf"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CHUNK_SIZE = 64 * 1024
PDF_PROBE_LOCK = Lock()
ROOT_MARKER = ".proofline-source-library-root"
ROOT_MARKER_VALUE = "proofline temporary source library v1\n"
SESSION_DIRECTORY_PATTERN = re.compile(r"^src-[A-Za-z0-9_-]{20,}$")


class LibraryError(Exception):
    def __init__(self, reason_code: str, status_code: int = 422) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.status_code = status_code


@dataclass
class StoredFile:
    metadata: SourceFileMetadata
    path: Path


@dataclass
class SessionRecord:
    session_id: str
    capability_digest: bytes
    csrf_digest: bytes
    created_at: datetime
    last_activity_at: datetime
    absolute_expires_at: datetime
    directory: Path
    state: str = "OPEN"
    files: dict[str, StoredFile] = field(default_factory=dict)
    source_material_sent_to_provider: bool = False
    deletion_receipt: SourceDeletionReceipt | None = None
    lock: RLock = field(default_factory=RLock)


@dataclass(frozen=True)
class Tombstone:
    capability_digest: bytes
    csrf_digest: bytes
    receipt: SourceDeletionReceipt


class SessionRepository(Protocol):
    """Atomic process-local session/tombstone persistence seam."""

    def create(self, record: SessionRecord) -> None: ...
    def get(self, session_id: str) -> SessionRecord | None: ...
    def expiry(self, record: SessionRecord, idle_ttl: timedelta) -> datetime: ...
    def touch(self, record: SessionRecord, now: datetime) -> None: ...
    def get_tombstone(self, session_id: str) -> Tombstone | None: ...
    def active_items(self) -> list[tuple[str, SessionRecord]]: ...
    def delete(self, record: SessionRecord, tombstone: Tombstone) -> None: ...
    def prune_tombstones(self, now: datetime) -> None: ...


class BlobStore(Protocol):
    """Opaque app-managed byte-storage seam; never exposes a static route."""

    root: Path

    def create_session_root(self, session_id: str) -> Path: ...
    def partial_path(self, directory: Path, file_id: str) -> Path: ...
    def commit(self, partial: Path, extension: str) -> Path: ...
    def open(self, path: Path) -> Path: ...
    def delete_file(self, path: Path) -> None: ...
    def delete_session_root(self, directory: Path) -> bool: ...
    def cleanup_orphans(self) -> None: ...


class ValidationService(Protocol):
    """Bounded structural validation seam; formulas and source content are never executed."""

    def validate(self, role: str, path: Path) -> None: ...


class ProcessSessionRepository:
    def __init__(self, *, tombstone_ttl: timedelta, max_tombstones: int) -> None:
        self.sessions: dict[str, SessionRecord] = {}
        self.tombstones: dict[str, Tombstone] = {}
        self.tombstone_ttl = tombstone_ttl
        self.max_tombstones = max_tombstones
        self.lock = RLock()

    def create(self, record: SessionRecord) -> None:
        with self.lock:
            self.sessions[record.session_id] = record

    def get(self, session_id: str) -> SessionRecord | None:
        with self.lock:
            return self.sessions.get(session_id)

    def expiry(self, record: SessionRecord, idle_ttl: timedelta) -> datetime:
        with record.lock:
            return min(record.last_activity_at + idle_ttl, record.absolute_expires_at)

    def touch(self, record: SessionRecord, now: datetime) -> None:
        with record.lock:
            record.last_activity_at = now

    def get_tombstone(self, session_id: str) -> Tombstone | None:
        with self.lock:
            return self.tombstones.get(session_id)

    def active_items(self) -> list[tuple[str, SessionRecord]]:
        with self.lock:
            return list(self.sessions.items())

    def delete(self, record: SessionRecord, tombstone: Tombstone) -> None:
        with self.lock:
            self.sessions.pop(record.session_id, None)
            self.tombstones[record.session_id] = tombstone
            self.prune_tombstones(datetime.now(UTC))

    def prune_tombstones(self, now: datetime) -> None:
        with self.lock:
            expired = [
                session_id
                for session_id, tombstone in self.tombstones.items()
                if now - tombstone.receipt.completed_at >= self.tombstone_ttl
            ]
            for session_id in expired:
                self.tombstones.pop(session_id, None)
            overflow = len(self.tombstones) - self.max_tombstones
            if overflow > 0:
                oldest = sorted(
                    self.tombstones,
                    key=lambda item: self.tombstones[item].receipt.completed_at,
                )[:overflow]
                for session_id in oldest:
                    self.tombstones.pop(session_id, None)


class TemporaryBlobStore:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise RuntimeError("source library root must be absolute")
        if root.is_symlink():
            raise RuntimeError("source library root must not be a symlink")
        resolved = root.resolve()
        forbidden = {Path("/"), Path.home().resolve(), Path.cwd().resolve()}
        if resolved in forbidden or len(resolved.parts) < 3:
            raise RuntimeError("source library root is too broad")
        self.root = resolved
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, stat.S_IRWXU)
        marker = self.root / ROOT_MARKER
        if marker.exists():
            if marker.is_symlink() or marker.read_text(encoding="utf-8") != ROOT_MARKER_VALUE:
                raise RuntimeError("source library root marker is invalid")
        else:
            unexpected = list(self.root.iterdir())
            if unexpected:
                raise RuntimeError("unmarked source library root is not empty")
            marker.write_text(ROOT_MARKER_VALUE, encoding="utf-8")
            os.chmod(marker, stat.S_IRUSR | stat.S_IWUSR)

    def create_session_root(self, session_id: str) -> Path:
        if not SESSION_DIRECTORY_PATTERN.fullmatch(session_id):
            raise RuntimeError("invalid opaque session identifier")
        directory = self.root / session_id
        directory.mkdir(mode=0o700)
        return directory

    def _validate_file_path(self, path: Path) -> None:
        if path.parent.parent != self.root or not SESSION_DIRECTORY_PATTERN.fullmatch(
            path.parent.name
        ):
            raise RuntimeError("refusing file operation outside app-managed session root")

    def partial_path(self, directory: Path, file_id: str) -> Path:
        if directory.parent != self.root or not file_id.startswith("file-"):
            raise RuntimeError("invalid opaque file target")
        path = directory / f"{file_id}.part"
        self._validate_file_path(path)
        return path

    def commit(self, partial: Path, extension: str) -> Path:
        self._validate_file_path(partial)
        if extension not in {".pdf", ".xlsx"} or partial.suffix != ".part":
            raise RuntimeError("invalid canonical file extension")
        final = partial.with_suffix(extension)
        partial.replace(final)
        return final

    def open(self, path: Path) -> Path:
        self._validate_file_path(path)
        if path.suffix not in {".pdf", ".xlsx"} or not path.is_file():
            raise LibraryError("FILE_NOT_FOUND", 404)
        return path

    def delete_file(self, path: Path) -> None:
        self._validate_file_path(path)
        path.unlink(missing_ok=True)

    def delete_session_root(self, directory: Path) -> bool:
        if directory.parent != self.root or not SESSION_DIRECTORY_PATTERN.fullmatch(directory.name):
            raise RuntimeError("refusing to delete outside app-managed session root")
        shutil.rmtree(directory, ignore_errors=True)
        return not directory.exists()

    def cleanup_orphans(self) -> None:
        for child in self.root.iterdir():
            if child.name == ROOT_MARKER:
                continue
            if not SESSION_DIRECTORY_PATTERN.fullmatch(child.name):
                raise RuntimeError("unexpected entry in app-managed source root")
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)


class SourceLibraryStore:
    """Single-process, single-worker temporary source storage.

    Session records and authorization capabilities intentionally exist only in this process.
    The filesystem root contains opaque session/file identifiers and is never served statically.
    """

    def __init__(
        self,
        root: Path | None = None,
        *,
        idle_ttl: timedelta = timedelta(minutes=30),
        absolute_ttl: timedelta = timedelta(hours=2),
        max_pdf_bytes: int = 20 * 1024 * 1024,
        max_xlsx_bytes: int = 10 * 1024 * 1024,
        probe_timeout_seconds: float = 5.0,
        tombstone_ttl: timedelta = timedelta(hours=2),
        max_tombstones: int = 1_000,
        repository: SessionRepository | None = None,
        blob_store: BlobStore | None = None,
        validation: ValidationService | None = None,
    ) -> None:
        configured_root = root or Path(tempfile.gettempdir()) / "proofline-source-library"
        self.idle_ttl = idle_ttl
        self.absolute_ttl = absolute_ttl
        self.max_pdf_bytes = max_pdf_bytes
        self.max_xlsx_bytes = max_xlsx_bytes
        self.probe_timeout_seconds = probe_timeout_seconds
        self.repository = repository or ProcessSessionRepository(
            tombstone_ttl=tombstone_ttl, max_tombstones=max_tombstones
        )
        self.blobs = blob_store or TemporaryBlobStore(configured_root)
        self.validation = validation or self
        self.root = self.blobs.root
        if isinstance(self.repository, ProcessSessionRepository):
            self._sessions = self.repository.sessions
            self._tombstones = self.repository.tombstones
            self._lock = self.repository.lock
        else:
            self._sessions = {}
            self._tombstones = {}
            self._lock = RLock()

    @staticmethod
    def _digest(value: str) -> bytes:
        return hashlib.sha256(value.encode("utf-8")).digest()

    def startup_cleanup(self) -> None:
        self.blobs.cleanup_orphans()

    def shutdown_cleanup(self) -> None:
        for session_id, _record in self.repository.active_items():
            self._delete_internal(session_id)

    def create(self, now: datetime | None = None) -> tuple[SourceSessionCreated, str]:
        now = now or datetime.now(UTC)
        session_id = f"src-{secrets.token_urlsafe(24)}"
        capability = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        directory = self.blobs.create_session_root(session_id)
        record = SessionRecord(
            session_id=session_id,
            capability_digest=self._digest(capability),
            csrf_digest=self._digest(csrf_token),
            created_at=now,
            last_activity_at=now,
            absolute_expires_at=now + self.absolute_ttl,
            directory=directory,
        )
        self.repository.create(record)
        status = self._status(record)
        return SourceSessionCreated(**status.model_dump(), csrf_token=csrf_token), capability

    def authorize(
        self,
        session_id: str,
        capability: str | None,
        *,
        csrf_token: str | None = None,
        require_csrf: bool = False,
        allow_deleted: bool = False,
    ) -> SessionRecord | Tombstone:
        if not capability:
            raise LibraryError("SESSION_CAPABILITY_REQUIRED", 401)
        self.repository.prune_tombstones(datetime.now(UTC))
        capability_digest = self._digest(capability)
        record = self.repository.get(session_id)
        tombstone = self.repository.get_tombstone(session_id)
        if record is None:
            if tombstone and hmac.compare_digest(tombstone.capability_digest, capability_digest):
                if require_csrf and (
                    not csrf_token
                    or not hmac.compare_digest(
                        tombstone.csrf_digest, self._digest(csrf_token)
                    )
                ):
                    raise LibraryError("CSRF_TOKEN_INVALID", 403)
                if allow_deleted:
                    return tombstone
                raise LibraryError("SESSION_GONE", 410)
            raise LibraryError("SESSION_NOT_FOUND", 404)
        if not hmac.compare_digest(record.capability_digest, capability_digest):
            raise LibraryError("SESSION_NOT_FOUND", 404)
        with record.lock:
            if allow_deleted and record.deletion_receipt is not None:
                if require_csrf and (
                    not csrf_token
                    or not hmac.compare_digest(
                        record.csrf_digest, self._digest(csrf_token)
                    )
                ):
                    raise LibraryError("CSRF_TOKEN_INVALID", 403)
                return Tombstone(
                    record.capability_digest,
                    record.csrf_digest,
                    record.deletion_receipt,
                )
            self._ensure_active(record)
            if require_csrf:
                if not csrf_token or not hmac.compare_digest(
                    record.csrf_digest, self._digest(csrf_token)
                ):
                    raise LibraryError("CSRF_TOKEN_INVALID", 403)
        return record

    def _expiry(self, record: SessionRecord) -> datetime:
        return self.repository.expiry(record, self.idle_ttl)

    def _ensure_active(self, record: SessionRecord, now: datetime | None = None) -> None:
        if record.state in {"DELETING", "DELETED"}:
            raise LibraryError("SESSION_GONE", 410)
        if (now or datetime.now(UTC)) >= self._expiry(record):
            self._delete_internal(record.session_id, record)
            raise LibraryError("SESSION_GONE", 410)

    def _touch(self, record: SessionRecord, now: datetime | None = None) -> None:
        activity_at = now or datetime.now(UTC)
        self._ensure_active(record, activity_at)
        self.repository.touch(record, activity_at)
        expiry = self._expiry(record)
        record.files = {
            file_id: StoredFile(
                metadata=stored.metadata.model_copy(update={"expires_at": expiry}),
                path=stored.path,
            )
            for file_id, stored in record.files.items()
        }

    def _status(self, record: SessionRecord) -> SourceSessionStatus:
        return SourceSessionStatus(
            session_id=record.session_id,
            state=record.state,
            created_at=record.created_at,
            last_activity_at=record.last_activity_at,
            idle_expires_at=record.last_activity_at + self.idle_ttl,
            absolute_expires_at=record.absolute_expires_at,
            files=tuple(stored.metadata for stored in record.files.values()),
        )

    def status(self, record: SessionRecord) -> SourceSessionStatus:
        with record.lock:
            self._touch(record)
            return self._status(record)

    @staticmethod
    def _safe_display_name(name: str | None) -> str:
        if not name or len(name) > 255:
            raise LibraryError("FILENAME_INVALID")
        if any(ord(char) < 32 for char in name) or "/" in name or "\\" in name:
            raise LibraryError("FILENAME_SUSPICIOUS")
        if name.startswith(".") or name.rstrip(". ") != name:
            raise LibraryError("FILENAME_SUSPICIOUS")
        return name

    async def upload(
        self, record: SessionRecord, role: str, upload: UploadFile
    ) -> SourceFileMetadata:
        if role not in {"report_pdf", "workbook"}:
            raise LibraryError("ROLE_INVALID")
        display_name = self._safe_display_name(upload.filename)
        suffix = Path(display_name).suffix.lower()
        expected_suffix = ".pdf" if role == "report_pdf" else ".xlsx"
        expected_mime = PDF_MIME if role == "report_pdf" else XLSX_MIME
        if suffix != expected_suffix:
            raise LibraryError("FILE_EXTENSION_NOT_ALLOWED")
        if upload.content_type != expected_mime:
            raise LibraryError("DECLARED_MIME_MISMATCH")
        max_bytes = self.max_pdf_bytes if role == "report_pdf" else self.max_xlsx_bytes
        file_id = f"file-{secrets.token_urlsafe(18)}"
        partial = self.blobs.partial_path(record.directory, file_id)
        final = partial.with_suffix(expected_suffix)
        with record.lock:
            self._ensure_active(record)
            if record.state != "OPEN":
                raise LibraryError("SESSION_NOT_OPEN", 409)
            if any(stored.metadata.role == role for stored in record.files.values()):
                raise LibraryError("ROLE_ALREADY_FILLED", 409)
            byte_count = 0
            try:
                with partial.open("xb") as target:
                    while chunk := await upload.read(CHUNK_SIZE):
                        byte_count += len(chunk)
                        if byte_count > max_bytes:
                            raise LibraryError("FILE_TOO_LARGE", 413)
                        target.write(chunk)
                if byte_count == 0:
                    raise LibraryError("FILE_EMPTY")
                self.validation.validate(role, partial)
                self._ensure_active(record)
                final = self.blobs.commit(partial, expected_suffix)
                now = datetime.now(UTC)
                self._touch(record, now)
                metadata = SourceFileMetadata(
                    file_id=file_id,
                    display_name=display_name,
                    canonical_type=expected_mime,
                    byte_count=byte_count,
                    uploaded_at=now,
                    validation_status="Ready",
                    role=role,
                    expires_at=self._expiry(record),
                )
                record.files[file_id] = StoredFile(metadata=metadata, path=final)
                return metadata
            except LibraryError:
                self.blobs.delete_file(partial)
                self.blobs.delete_file(final)
                raise
            except Exception as error:
                self.blobs.delete_file(partial)
                self.blobs.delete_file(final)
                raise LibraryError("FILE_VALIDATION_FAILED") from error
            finally:
                await upload.close()

    def validate(self, role: str, path: Path) -> None:
        started = time.monotonic()
        if role == "report_pdf":
            self._probe_pdf(path, started)
        elif role == "workbook":
            self._probe_xlsx(path, started)
        else:
            raise LibraryError("ROLE_INVALID")

    def _check_timeout(self, started: float) -> None:
        if time.monotonic() - started > self.probe_timeout_seconds:
            raise LibraryError("VALIDATION_TIMEOUT")

    def _probe_pdf(self, path: Path, started: float) -> None:
        with path.open("rb") as source:
            header = source.read(8)
            source.seek(max(0, path.stat().st_size - 2048))
            trailer = source.read()
        if not header.startswith(b"%PDF-") or b"%%EOF" not in trailer:
            raise LibraryError("PDF_MAGIC_INVALID")
        logger = logging.getLogger("pypdf")
        with PDF_PROBE_LOCK:
            previous_handlers = logger.handlers
            previous_level = logger.level
            previous_propagate = logger.propagate
            logger.handlers = [logging.NullHandler()]
            logger.setLevel(logging.CRITICAL + 1)
            logger.propagate = False
            try:
                self._probe_pdf_structure(path, started)
                self._check_timeout(started)
            finally:
                logger.handlers = previous_handlers
                logger.setLevel(previous_level)
                logger.propagate = previous_propagate

    def _probe_pdf_structure(self, path: Path, started: float) -> None:
        try:
            reader = PdfReader(path, strict=True)
            self._check_timeout(started)
            if reader.is_encrypted:
                raise LibraryError("PASSWORD_PROTECTED_INPUT")
            if len(reader.pages) == 0 or len(reader.pages) > 500:
                raise LibraryError("PDF_PAGE_LIMIT")
            self._check_timeout(started)
            self._reject_pdf_active_content(reader, started)
            text_bytes = 0
            for page in reader.pages:
                self._check_timeout(started)
                text_bytes += len((page.extract_text() or "").encode("utf-8", errors="ignore"))
                self._check_timeout(started)
                if text_bytes > 5 * 1024 * 1024:
                    raise LibraryError("PDF_TEXT_LIMIT")
        except LibraryError:
            raise
        except Exception as error:
            raise LibraryError("PDF_STRUCTURE_UNSUPPORTED") from error

    def _reject_pdf_active_content(self, reader: PdfReader, started: float) -> None:
        forbidden_keys = {
            "/A",
            "/AA",
            "/AcroForm",
            "/EmbeddedFiles",
            "/Filespec",
            "/JavaScript",
            "/JS",
            "/Launch",
            "/OpenAction",
            "/RichMedia",
            "/URI",
            "/XFA",
        }
        forbidden_actions = {
            "/GoTo",
            "/GoTo3DView",
            "/GoToE",
            "/GoToR",
            "/Hide",
            "/ImportData",
            "/JavaScript",
            "/Launch",
            "/Movie",
            "/Named",
            "/Rendition",
            "/ResetForm",
            "/RichMediaExecute",
            "/SetOCGState",
            "/Sound",
            "/SubmitForm",
            "/Thread",
            "/Trans",
            "/URI",
        }
        forbidden_types = {
            "/3D",
            "/EmbeddedFile",
            "/FileAttachment",
            "/Filespec",
            "/Movie",
            "/RichMedia",
            "/Screen",
            "/Sound",
            "/Widget",
        }
        stack = [reader.trailer]
        seen: set[tuple[int, int] | int] = set()
        inspected = 0
        while stack:
            self._check_timeout(started)
            value = stack.pop()
            if isinstance(value, IndirectObject):
                identity = (value.idnum, value.generation)
                if identity in seen:
                    continue
                seen.add(identity)
                value = value.get_object()
            elif isinstance(value, DictionaryObject | ArrayObject):
                identity = id(value)
                if identity in seen:
                    continue
                seen.add(identity)
            inspected += 1
            if inspected > 10_000:
                raise LibraryError("PDF_STRUCTURE_UNSUPPORTED")
            if isinstance(value, DictionaryObject):
                keys = {str(key) for key in value.keys()}
                object_type = str(value.get("/Type", ""))
                object_subtype = str(value.get("/Subtype", ""))
                if (
                    keys & forbidden_keys
                    or str(value.get("/S", "")) in forbidden_actions
                    or object_type in forbidden_types
                    or object_subtype in forbidden_types
                ):
                    raise LibraryError("PDF_ACTIVE_CONTENT")
                stack.extend(value.values())
            elif isinstance(value, ArrayObject):
                stack.extend(value)

    def _probe_xlsx(self, path: Path, started: float) -> None:
        with path.open("rb") as source:
            magic = source.read(4)
        if magic != b"PK\x03\x04":
            raise LibraryError("XLSX_MAGIC_INVALID")
        try:
            archive = zipfile.ZipFile(path)
        except zipfile.BadZipFile as error:
            raise LibraryError("XLSX_ARCHIVE_INVALID") from error
        with archive:
            infos = archive.infolist()
            self._check_timeout(started)
            if len(infos) > 2_000:
                raise LibraryError("ARCHIVE_ENTRY_LIMIT")
            total_uncompressed = 0
            names: set[str] = set()
            for info in infos:
                self._check_timeout(started)
                name = info.filename
                pure = PurePosixPath(name)
                if (
                    not name
                    or name.startswith(("/", "\\"))
                    or "\\" in name
                    or ":" in name
                    or ".." in pure.parts
                    or pure.parts[0] not in {"[Content_Types].xml", "_rels", "docProps", "xl"}
                ):
                    raise LibraryError("ARCHIVE_PATH_SUSPICIOUS")
                if name in names:
                    raise LibraryError("ARCHIVE_PATH_SUSPICIOUS")
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise LibraryError("ARCHIVE_PATH_SUSPICIOUS")
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise LibraryError("ARCHIVE_COMPRESSION_UNSUPPORTED")
                if info.flag_bits & 0x1:
                    raise LibraryError("PASSWORD_PROTECTED_INPUT")
                if info.file_size > 25 * 1024 * 1024:
                    raise LibraryError("ARCHIVE_ENTRY_TOO_LARGE")
                if info.compress_size and info.file_size / info.compress_size > 100:
                    raise LibraryError("ZIP_BOMB_DETECTED")
                total_uncompressed += info.file_size
                if total_uncompressed > 50 * 1024 * 1024:
                    raise LibraryError("ZIP_BOMB_DETECTED")
                lowered = name.lower()
                if "vbaproject" in lowered or lowered.endswith(".bin"):
                    raise LibraryError("MACROS_NOT_ALLOWED")
                if lowered.startswith("xl/externallinks/"):
                    raise LibraryError("EXTERNAL_LINKS_NOT_ALLOWED")
                if lowered == "xl/connections.xml" or lowered.startswith("xl/querytables/"):
                    raise LibraryError("EXTERNAL_LINKS_NOT_ALLOWED")
                if lowered.endswith((".zip", ".xlsx", ".xlsm", ".xlsb", ".ods")):
                    raise LibraryError("NESTED_ARCHIVE_NOT_ALLOWED")
                allowed_suffixes = {
                    "",
                    ".xml",
                    ".rels",
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".emf",
                    ".wmf",
                }
                if Path(lowered).suffix not in allowed_suffixes:
                    raise LibraryError("ARCHIVE_ENTRY_UNEXPECTED")
                names.add(name)
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise LibraryError("XLSX_STRUCTURE_INVALID")
            content_types = self._probe_xml_member(archive, "[Content_Types].xml", started)
            self._check_timeout(started)
            for node in content_types.iter():
                content_type = next(
                    (
                        value.lower()
                        for key, value in node.attrib.items()
                        if key.endswith("ContentType")
                    ),
                    "",
                )
                if any(
                    marker in content_type
                    for marker in ("connection", "external", "macro", "querytable", "vba")
                ):
                    raise LibraryError("MACROS_NOT_ALLOWED")
            workbook = self._probe_xml_member(archive, "xl/workbook.xml", started)
            self._check_timeout(started)
            sheet_count = sum(1 for node in workbook.iter() if node.tag.endswith("}sheet"))
            if sheet_count == 0 or sheet_count > 100:
                raise LibraryError("WORKBOOK_SHEET_LIMIT")
            for info in infos:
                lowered = info.filename.lower()
                if lowered.endswith(".rels"):
                    payload = archive.read(info)
                    self._check_timeout(started)
                    relationships = self._parse_xml(payload)
                    self._check_timeout(started)
                    for relationship in relationships.iter():
                        is_relationship = relationship.tag.endswith("}Relationship") or (
                            relationship.tag == "Relationship"
                        )
                        if is_relationship:
                            relationship_type = next(
                                (
                                    value
                                    for key, value in relationship.attrib.items()
                                    if key.endswith("Type")
                                ),
                                "",
                            ).lower()
                            target_mode = next(
                                (
                                    value
                                    for key, value in relationship.attrib.items()
                                    if key.endswith("TargetMode")
                                ),
                                "",
                            )
                            if target_mode.strip().lower() == "external":
                                raise LibraryError("EXTERNAL_LINKS_NOT_ALLOWED")
                            if any(
                                marker in relationship_type
                                for marker in (
                                    "connection",
                                    "externallink",
                                    "oleobject",
                                    "querytable",
                                    "vbaproject",
                                )
                            ):
                                raise LibraryError("EXTERNAL_LINKS_NOT_ALLOWED")
                if lowered.startswith("xl/worksheets/") and lowered.endswith(".xml"):
                    payload = archive.read(info)
                    self._check_timeout(started)
                    self._probe_sheet(payload, started)
                    self._check_timeout(started)
                if lowered == "xl/sharedstrings.xml":
                    payload = archive.read(info)
                    self._check_timeout(started)
                    shared_strings = self._parse_xml(payload)
                    self._check_timeout(started)
                    shared_text_bytes = sum(
                        len((node.text or "").encode("utf-8", errors="ignore"))
                        for node in shared_strings.iter()
                    )
                    if shared_text_bytes > 5 * 1024 * 1024:
                        raise LibraryError("WORKBOOK_TEXT_LIMIT")

    @staticmethod
    def _reject_unsafe_xml(payload: bytes) -> None:
        upper = payload.upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise LibraryError("XML_DECLARATION_NOT_ALLOWED")

    def _probe_xml_member(
        self, archive: zipfile.ZipFile, name: str, started: float
    ) -> ElementTree.Element:
        self._check_timeout(started)
        payload = archive.read(name)
        self._check_timeout(started)
        self._reject_unsafe_xml(payload)
        parsed = self._parse_xml(payload)
        self._check_timeout(started)
        return parsed

    def _parse_xml(self, payload: bytes) -> ElementTree.Element:
        self._reject_unsafe_xml(payload)
        try:
            return ElementTree.fromstring(payload)
        except ElementTree.ParseError as error:
            raise LibraryError("XLSX_XML_INVALID") from error

    def _probe_sheet(self, payload: bytes, started: float) -> None:
        self._reject_unsafe_xml(payload)
        cell_count = 0
        text_bytes = 0
        max_row = 0
        max_column = 0
        try:
            for _event, node in ElementTree.iterparse(io.BytesIO(payload), events=("end",)):
                self._check_timeout(started)
                if node.tag.endswith("}c"):
                    cell_count += 1
                    reference = node.attrib.get("r", "")
                    match = re.fullmatch(r"([A-Z]{1,4})([1-9][0-9]*)", reference)
                    if match:
                        column = 0
                        for char in match.group(1):
                            column = column * 26 + ord(char) - 64
                        max_column = max(max_column, column)
                        max_row = max(max_row, int(match.group(2)))
                if node.text:
                    text_bytes += len(node.text.encode("utf-8", errors="ignore"))
                node.clear()
        except ElementTree.ParseError as error:
            raise LibraryError("XLSX_XML_INVALID") from error
        if cell_count > 200_000 or max_row > 50_000 or max_column > 500:
            raise LibraryError("WORKBOOK_DIMENSION_LIMIT")
        if text_bytes > 5 * 1024 * 1024:
            raise LibraryError("WORKBOOK_TEXT_LIMIT")

    def list_files(self, record: SessionRecord) -> tuple[SourceFileMetadata, ...]:
        with record.lock:
            self._touch(record)
            return tuple(stored.metadata for stored in record.files.values())

    def get_file(self, record: SessionRecord, file_id: str) -> StoredFile:
        with record.lock:
            self._ensure_active(record)
            stored = record.files.get(file_id)
            if stored is None:
                raise LibraryError("FILE_NOT_FOUND", 404)
            self._touch(record)
            self.blobs.open(stored.path)
            return stored

    def remove_file(self, record: SessionRecord, file_id: str) -> SourceFileMetadata:
        with record.lock:
            self._ensure_active(record)
            if record.state != "OPEN":
                raise LibraryError("SESSION_NOT_OPEN", 409)
            stored = record.files.pop(file_id, None)
            if stored is None:
                raise LibraryError("FILE_NOT_FOUND", 404)
            self.blobs.delete_file(stored.path)
            self._touch(record)
            return stored.metadata

    def mark_provider_transfer_started(self, record: SessionRecord) -> None:
        """Call immediately before any future provider transfer, including failing attempts."""
        with record.lock:
            self._ensure_active(record)
            record.source_material_sent_to_provider = True

    def start(self, record: SessionRecord) -> SourceSessionStatus:
        with record.lock:
            self._touch(record)
            ready_roles = {
                stored.metadata.role
                for stored in record.files.values()
                if stored.metadata.validation_status == "Ready"
            }
            if ready_roles != {"report_pdf", "workbook"}:
                raise LibraryError("REQUIRED_FILES_NOT_READY", 409)
            # Transport/workers are intentionally absent in this slice. Secret presence alone
            # must never imply provider availability or false PROCESSING progress.
            raise LibraryError("PROVIDER_ACCESS_REQUIRED", 503)

    def delete(
        self, session_id: str, capability: str | None, csrf_token: str | None
    ) -> SourceDeletionReceipt:
        authorized = self.authorize(
            session_id,
            capability,
            csrf_token=csrf_token,
            require_csrf=True,
            allow_deleted=True,
        )
        if isinstance(authorized, Tombstone):
            return authorized.receipt
        return self._delete_internal(session_id, authorized)

    def _delete_internal(
        self, session_id: str, record: SessionRecord | None = None
    ) -> SourceDeletionReceipt:
        if record is None:
            record = self.repository.get(session_id)
        if record is None:
            raise LibraryError("SESSION_NOT_FOUND", 404)
        requested_at = datetime.now(UTC)
        with record.lock:
            if record.deletion_receipt is not None:
                return record.deletion_receipt
            record.state = "DELETING"
            file_count = len(record.files)
            file_bytes = sum(stored.metadata.byte_count for stored in record.files.values())
            directory_gone = self.blobs.delete_session_root(record.directory)
            record.files.clear()
            record.state = "DELETED"
            completed_at = datetime.now(UTC)
            receipt = SourceDeletionReceipt(
                receipt_id=f"receipt-{secrets.token_urlsafe(18)}",
                session_id=session_id,
                requested_at=requested_at,
                completed_at=completed_at,
                status="complete" if directory_gone else "partial",
                removed={
                    "source_files": RemovalCount(count=file_count, bytes=file_bytes),
                    "derived_artifacts": RemovalCount(count=0, bytes=0),
                    "session_metadata": RemovalCount(count=1, bytes=0),
                },
                app_managed_directory_gone=directory_gone,
                source_material_sent_to_provider=record.source_material_sent_to_provider,
            )
            record.deletion_receipt = receipt
            self.repository.delete(
                record,
                Tombstone(record.capability_digest, record.csrf_digest, receipt),
            )
        return receipt

    def cleanup_expired(self, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        candidates = self.repository.active_items()
        deleted = 0
        for session_id, record in candidates:
            with record.lock:
                if record.state not in {"DELETING", "DELETED"} and now >= self._expiry(record):
                    self._delete_internal(session_id, record)
                    deleted += 1
        return deleted
