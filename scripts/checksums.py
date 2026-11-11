"""Gera o SHA256SUMS dos arquivos de uma pasta, no formato aceito por `sha256sum -c`.

Uso: python scripts/checksums.py dist
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

OUTPUT_NAME = "SHA256SUMS"
CHUNK_SIZE = 1024 * 1024


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(folder: Path) -> Path:
    files = sorted(item for item in folder.iterdir() if item.is_file() and item.name != OUTPUT_NAME)
    if not files:
        raise SystemExit(f"Nenhum arquivo em {folder}")
    lines = [f"{sha256_of(item)}  {item.name}\n" for item in files]
    output = folder / OUTPUT_NAME
    # newline="\n": no Windows o padrão vira CRLF e o `sha256sum -c` lê "cofre\r" como nome.
    output.write_text("".join(lines), encoding="utf-8", newline="\n")
    return output


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    print(write_checksums(Path(sys.argv[1])).read_text(encoding="utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
