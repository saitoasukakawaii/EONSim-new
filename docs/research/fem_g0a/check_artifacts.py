"""Read-only FEM-G0A syntax/link/provenance checks, Python standard library only.

Does not execute a build, solver, existing project test, or external command.
Not a general Markdown parser: checks inline file links and fenced code balance.
Text is UTF-8; source hashes normalize checkout CRLF to the audited Git LF.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[3]
SHA = "f44c3e0e81f090637f6f21a7b63a9d12d3e30424"
MARKDOWN = (
    "docs/architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md",
    "docs/architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md",
    "docs/development/CODEX_PROGRESS.md",
    "docs/development/CODEX_TASK_QUEUE.md",
    "docs/development/CODEX_SESSION_LOG.md",
    "docs/research/KNOWLEDGE_LOG.md",
    "website/drafts/dof-semantics-and-nested-fsi-blocks.md",
)


def source_digest(data):
    """Ignore Git's checkout line endings, but retain all other source bytes."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def main():
    errors, local_count, source_count = [], 0, 0
    for filename in MARKDOWN:
        path = ROOT / filename
        text = path.read_text(encoding="utf-8")
        fence = None
        prose = []
        for line_no, line in enumerate(text.splitlines(), 1):
            match = re.match(r"^\s*(`{3,}|~{3,})", line)
            if match:
                token = match[1]
                if fence is None:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = None
                continue
            if fence is None:
                prose.append(line)
        if fence is not None:
            errors.append(f"{filename}: unclosed fence")
        for target in re.findall(r"\[[^\]\n]*\]\(([^)\s]+)\)", "\n".join(prose)):
            url = urlsplit(target)
            if url.scheme:
                prefix = "https://github.com/saitoasukakawaii/EONSim-new/blob/"
                # Existing historical links elsewhere have their own commits.
                if filename.endswith(("FEM_G0A_DOF_AND_BLOCK_DESIGN.md", "dof-semantics-and-nested-fsi-blocks.md")) and target.startswith(prefix):
                    commit, file = unquote(url.path).split("/blob/", 1)[1].split("/", 1)
                    if commit != SHA:
                        errors.append(f"{filename}: wrong fixed source SHA: {target}")
                        continue
                    source = ROOT / file
                    if not source.is_file():
                        errors.append(f"{filename}: missing source path: {target}")
                        continue
                    source_count += 1
                    if url.fragment:
                        match = re.fullmatch(r"L(\d+)(?:-L(\d+))?", url.fragment)
                        if not match:
                            errors.append(f"{filename}: malformed line anchor: {target}")
                        else:
                            first, last = int(match[1]), int(match[2] or match[1])
                            if not 1 <= first <= last <= len(source.read_text(encoding="utf-8").splitlines()):
                                errors.append(f"{filename}: invalid source lines: {target}")
                continue
            if not url.path:
                continue  # no local anchor-only links are introduced in this task
            local_count += 1
            if url.path.startswith("/"):
                route = ROOT / "website" / unquote(url.path).lstrip("/")
                exists = route.exists() or route.with_suffix(".md").is_file() or (route / "index.md").is_file()
            else:
                exists = (path.parent / unquote(url.path)).exists()
            if not exists:
                errors.append(f"{filename}: missing file link: {target}")
    scripts = sorted((ROOT / "docs/research/fem_g0a").glob("*.py"))
    for path in scripts:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    evidence = ROOT / "docs/research/data/fem-g0a-2026-10-30"
    baseline = json.loads((evidence / "baseline.json").read_text(encoding="utf-8"))
    for filename, expected in baseline["source_sha256"].items():
        actual = source_digest((ROOT / filename).read_bytes())
        if expected != actual:
            errors.append(f"production source changed since audit: {filename}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: AST syntax for {len(scripts)} standard-library Python files")
    print(f"PASS: balanced Markdown fences in {len(MARKDOWN)} files")
    print(f"PASS: {local_count} local file/site-route links (source existence only)")
    print(f"PASS: {source_count} fixed EONSim SHA/path/line references")
    print(f"PASS: {len(baseline['source_sha256'])} audited production source hashes unchanged (LF-normalized)")
    print("Scope: no remote link liveness, Markdown rendering, build, MPI, or solver check")


if __name__ == "__main__":
    main()
