"""Utilities for shrinking oversized `.docx` files before upload."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image


@dataclass
class DocxCompressionResult:
    """Compression result for a `.docx` file."""

    source_path: Path
    output_path: Path
    original_size: int
    compressed_size: int
    changed_entries: List[str] = field(default_factory=list)
    target_met: bool = False
    max_image_width: int = 1600


class DocxCompressor:
    """Compress embedded images inside a `.docx` archive."""

    def __init__(self, width_candidates: Sequence[int] = (1600, 1400, 1200, 1000, 800)) -> None:
        self.width_candidates = tuple(width_candidates)

    def compress(
        self,
        source_path: Path,
        output_path: Path,
        max_image_width: int = 1600,
    ) -> DocxCompressionResult:
        source = Path(source_path)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        changed_entries: List[str] = []
        with ZipFile(source, "r") as zin, ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename.startswith("word/media/") and info.filename.lower().endswith(".png"):
                    compressed = self._compress_png(data, max_image_width=max_image_width)
                    if compressed is not None and len(compressed) < len(data):
                        data = compressed
                        changed_entries.append(info.filename)
                zout.writestr(info, data)

        return DocxCompressionResult(
            source_path=source,
            output_path=output,
            original_size=source.stat().st_size,
            compressed_size=output.stat().st_size,
            changed_entries=changed_entries,
            max_image_width=max_image_width,
        )

    def compress_to_target(
        self,
        source_path: Path,
        output_path: Path,
        target_max_bytes: int,
    ) -> DocxCompressionResult:
        source = Path(source_path)
        best_result: DocxCompressionResult | None = None

        for index, width in enumerate(self.width_candidates):
            candidate_path = output_path if index == len(self.width_candidates) - 1 else output_path.with_name(
                f"{output_path.stem}-{width}{output_path.suffix}"
            )
            result = self.compress(source, candidate_path, max_image_width=width)
            result.target_met = result.compressed_size <= target_max_bytes
            if best_result is None or result.compressed_size < best_result.compressed_size:
                best_result = result
            if result.target_met:
                break

        assert best_result is not None
        if best_result.output_path != output_path:
            output_path.write_bytes(best_result.output_path.read_bytes())
            best_result = DocxCompressionResult(
                source_path=best_result.source_path,
                output_path=output_path,
                original_size=best_result.original_size,
                compressed_size=output_path.stat().st_size,
                changed_entries=best_result.changed_entries,
                target_met=best_result.compressed_size <= target_max_bytes,
                max_image_width=best_result.max_image_width,
            )
        return best_result

    def _compress_png(self, data: bytes, max_image_width: int) -> bytes | None:
        try:
            image = Image.open(io.BytesIO(data))
        except Exception:
            return None

        if image.width > max_image_width:
            ratio = max_image_width / image.width
            image = image.resize(
                (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
                Image.LANCZOS,
            )

        output = io.BytesIO()
        save_kwargs = {"format": "PNG", "optimize": True, "compress_level": 9}
        image.save(output, **save_kwargs)
        return output.getvalue()
