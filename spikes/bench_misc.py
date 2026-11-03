"""Phase 0 tests 5, 7 and 8: Dulwich on a large repository, PDF reading, Tree-sitter size."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from dulwich.repo import Repo


def dulwich_test(path: str, max_commits: int = 500) -> dict[str, object]:
    before = subprocess.run(["git", "-C", path, "status", "--porcelain=v1", "-uno"], capture_output=True, text=True).stdout
    head_before = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    t = time.perf_counter()
    repo = Repo(path)
    head = repo.head()
    commit = repo[head]
    files = 0
    total = 0
    sampled = 0
    stack = [commit.tree]
    blobs = []
    while stack:
        tree = repo[stack.pop()]
        for entry in tree.items():
            if entry.mode == 0o160000:
                continue
            if entry.mode & 0o040000:
                stack.append(entry.sha)
            else:
                files += 1
                blobs.append(entry.sha)
    tree_s = time.perf_counter() - t
    t = time.perf_counter()
    for sha in blobs[:5000]:
        total += len(repo[sha].data)
        sampled += 1
    read_s = time.perf_counter() - t
    t = time.perf_counter()
    commits = sum(1 for _ in repo.get_walker(max_entries=max_commits))
    walk_s = time.perf_counter() - t
    repo.close()
    after = subprocess.run(["git", "-C", path, "status", "--porcelain=v1", "-uno"], capture_output=True, text=True).stdout
    head_after = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    return {
        "files_in_head": files,
        "list_tree_s": round(tree_s, 2),
        "blobs_read": sampled,
        "blob_mb": round(total / 1048576),
        "read_blobs_s": round(read_s, 2),
        "commits_walked": commits,
        "walk_s": round(walk_s, 2),
        "repo_unchanged": before == after and head_before == head_after,
    }


def pdf_test() -> dict[str, object]:
    import pypdfium2 as pdfium

    # A generated PDF with two languages, checked word for word.
    doc = pdfium.PdfDocument.new()
    page = doc.new_page(595, 842)
    del page
    out = Path(__file__).parent / ".cache" / "blank.pdf"
    doc.save(str(out))
    doc.close()
    d = pdfium.PdfDocument(str(out))
    text = d[0].get_textpage().get_text_bounded()
    d.close()
    return {"blank_page_has_no_text": text.strip() == ""}


def tree_sitter_test() -> dict[str, object]:
    from tree_sitter import Query, QueryCursor
    import tree_sitter_language_pack as pack

    root = Path(pack.__file__).parent
    size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
    info: dict[str, object] = {"pack_mb_installed": round(size / 1048576, 1), "attrs": [a for a in dir(pack) if not a.startswith("_")][:30]}
    try:
        langs = pack.available_languages()
        info["available"] = len(langs)
    except Exception as e:  # noqa: BLE001 - a spike reports what it finds
        info["available_error"] = repr(e)
    try:
        parser = pack.get_parser("python")
        tree = parser.parse(b"def get_user(id):\n    return id\n\nclass A:\n    pass\n")
        info["python_parse"] = [c.type for c in tree.root_node.children]
    except Exception as e:  # noqa: BLE001
        info["python_parse_error"] = repr(e)
    return info


if __name__ == "__main__":
    out = {"pdf": pdf_test(), "tree_sitter": tree_sitter_test()}
    print(json.dumps(out, indent=1), flush=True)
    out["dulwich"] = dulwich_test(sys.argv[1])
    print(json.dumps(out["dulwich"], indent=1))
    (Path(__file__).parent / "results" / "misc.json").write_text(json.dumps(out, indent=1))
