"""Verify that a packaged Windows backend is a self-consistent CPU-only build."""
from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path


CUDA_PATTERN = re.compile(
    r"(?:c10_cuda|torch_cuda|cudart|cublas|cudnn|cufft|curand|"
    r"cusolver|cusparse|nvrtc|nvjitlink|nvtoolsext|nvperf|cupti|nvcuda)",
    re.IGNORECASE,
)


def _read_c_string(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        raise ValueError(f"string offset outside file: {offset}")
    end = data.find(b"\0", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("ascii", errors="replace")


def read_pe_imports(path: Path) -> list[str]:
    """Return imported DLL names from a PE32/PE32+ file."""

    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError("missing DOS header")

    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError("missing PE header")

    coff_offset = pe_offset + 4
    section_count = struct.unpack_from("<H", data, coff_offset + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff_offset + 16)[0]
    optional_offset = coff_offset + 20
    if optional_offset + optional_size > len(data):
        raise ValueError("truncated optional header")

    magic = struct.unpack_from("<H", data, optional_offset)[0]
    if magic == 0x10B:
        data_directory_offset = optional_offset + 96
        rva_count_offset = optional_offset + 92
    elif magic == 0x20B:
        data_directory_offset = optional_offset + 112
        rva_count_offset = optional_offset + 108
    else:
        raise ValueError(f"unsupported optional-header magic: {magic:#x}")

    rva_count = struct.unpack_from("<I", data, rva_count_offset)[0]
    if rva_count <= 1:
        return []

    import_directory_offset = data_directory_offset + 8
    import_rva, import_size = struct.unpack_from("<II", data, import_directory_offset)
    if not import_rva or not import_size:
        return []

    section_offset = optional_offset + optional_size
    sections: list[tuple[int, int, int, int]] = []
    for index in range(section_count):
        offset = section_offset + index * 40
        if offset + 40 > len(data):
            raise ValueError("truncated section table")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, offset + 8
        )
        sections.append((virtual_address, virtual_size, raw_offset, raw_size))

    size_of_headers = struct.unpack_from("<I", data, optional_offset + 60)[0]

    def rva_to_offset(rva: int) -> int:
        if rva < size_of_headers:
            return rva
        for virtual_address, virtual_size, raw_offset, raw_size in sections:
            span = max(virtual_size, raw_size)
            if virtual_address <= rva < virtual_address + span:
                result = raw_offset + (rva - virtual_address)
                if result < len(data):
                    return result
        raise ValueError(f"RVA outside mapped sections: {rva:#x}")

    descriptor_offset = rva_to_offset(import_rva)
    imports: list[str] = []
    max_descriptors = max(1, import_size // 20 + 1)
    for index in range(max_descriptors):
        offset = descriptor_offset + index * 20
        if offset + 20 > len(data):
            raise ValueError("truncated import descriptor")
        descriptor = struct.unpack_from("<IIIII", data, offset)
        if descriptor == (0, 0, 0, 0, 0):
            break
        name_rva = descriptor[3]
        imports.append(_read_c_string(data, rva_to_offset(name_rva)))
    return imports


def verify_build(root: Path) -> tuple[list[str], list[str], int]:
    root = root.resolve()
    if not root.is_dir():
        return [f"build root not found: {root}"], [], 0

    offenders: list[str] = []
    parse_errors: list[str] = []
    checked = 0

    torch_lib = root / "_internal" / "torch" / "lib"
    for required in ("torch_cpu.dll", "shm.dll"):
        if not (torch_lib / required).is_file():
            offenders.append(f"required CPU torch DLL missing: {torch_lib / required}")

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".dll", ".exe"}:
            continue
        checked += 1
        relative = path.relative_to(root)
        relative_text = str(relative)
        if CUDA_PATTERN.search(path.name) or "nvidia" in {
            part.lower() for part in relative.parts
        }:
            offenders.append(f"CUDA/NVIDIA binary bundled: {relative_text}")

        try:
            imports = read_pe_imports(path)
        except ValueError as exc:
            parse_errors.append(f"{relative_text}: {exc}")
            continue
        cuda_imports = sorted({name for name in imports if CUDA_PATTERN.search(name)})
        if cuda_imports:
            offenders.append(
                f"CUDA dependency referenced by {relative_text}: {', '.join(cuda_imports)}"
            )

    return offenders, parse_errors, checked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()

    offenders, parse_errors, checked = verify_build(args.root)
    print(f"[cpu-build-check] inspected {checked} PE binaries")

    if parse_errors:
        print("[cpu-build-check] unable to inspect:")
        for item in parse_errors:
            print(f"  - {item}")

    if offenders:
        print("[cpu-build-check] FAILED")
        for item in offenders:
            print(f"  - {item}")
        return 1

    if parse_errors:
        print("[cpu-build-check] FAILED because some PE imports could not be verified")
        return 1

    print("[cpu-build-check] CPU-only binary set confirmed; no CUDA imports found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
