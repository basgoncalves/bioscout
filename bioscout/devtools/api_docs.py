"""Build the browsable API reference in docs/api/ (GitHub-rendered Markdown).

    python -m bioscout.devtools.api_docs

Reads the source with ``ast`` -- nothing is imported, so it runs without
OpenSim, CEINMS or a display. For every public module it writes one page:
the module summary, a clickable list of its functions and classes, and for
each one the call signature, an inputs table (name, type, default), the
return type, the docstring and a link to the source line on GitHub.
docs/api/index.md lists every module, grouped by package.
"""
import ast
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "bioscout"
OUT = ROOT / "docs" / "api"
GITHUB = "https://github.com/basgoncalves/bioscout/blob/main/"
SKIP_DIRS = {"tests", "__pycache__", "bin", "templates", "setup_files", "models", "logs", "config", "pyosim"}
#: package order on the index page (the order a run touches them); anything else follows A-Z
ORDER = ["bioscout", "bioscout.session", "bioscout.core", "bioscout.simulate", "bioscout.model", "bioscout.results",
         "bioscout.emg", "bioscout.plot", "bioscout.utils", "bioscout.lab", "bioscout.pipeline", "bioscout.cli"]


def modules():
    for p in sorted(PKG.rglob("*.py")):
        rel = p.relative_to(ROOT)
        parts = rel.with_suffix("").parts
        if any(d in SKIP_DIRS for d in parts[:-1]) or any(x.startswith("_") and x != "__init__" for x in parts):
            continue
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        yield name, p


def first_line(doc):
    return (doc or "").strip().split("\n\n")[0].replace("\n", " ").strip()


def anchor(s):
    return re.sub(r"[^a-z0-9_-]", "", s.lower().replace(" ", "-"))


def ann(node):
    return ast.unparse(node) if node is not None else ""


def args_table(fn, skip_self):
    a = fn.args
    rows = []
    pos = a.posonlyargs + a.args
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    for arg, d in zip(pos, defaults):
        rows.append((arg.arg, ann(arg.annotation), "" if d is None else ast.unparse(d)))
    if a.vararg:
        rows.append(("*" + a.vararg.arg, ann(a.vararg.annotation), ""))
    for arg, d in zip(a.kwonlyargs, a.kw_defaults):
        rows.append((arg.arg, ann(arg.annotation), "" if d is None else ast.unparse(d)))
    if a.kwarg:
        rows.append(("**" + a.kwarg.arg, ann(a.kwarg.annotation), ""))
    if skip_self and rows and rows[0][0] in ("self", "cls"):
        rows = rows[1:]
    return rows


def signature(name, fn, skip_self):
    parts = []
    for n, t, d in args_table(fn, skip_self):
        s = n + (f": {t}" if t else "") + ((f" = {d}" if t else f"={d}") if d else "")
        parts.append(s)
    ret = f" -> {ann(fn.returns)}" if fn.returns is not None else ""
    one = f"{name}({', '.join(parts)}){ret}"
    if len(one) <= 90:
        return one
    return f"{name}(\n    " + ",\n    ".join(parts) + f"\n){ret}"


def esc_cell(s):
    return s.replace("|", "\\|").replace("\n", " ")


def doc_md(doc):
    """Docstring -> Markdown: section headings (numpy / Google style) in bold, the rest kept as written."""
    if not doc:
        return "_No docstring._\n"
    lines = doc.strip("\n").split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if re.fullmatch(r"\s*-{3,}\s*", nxt) and ln.strip():          # numpy style: Title / -----
            out.append(f"\n**{ln.strip()}**\n"); i += 2; continue
        m = re.fullmatch(r"\s*(Args|Arguments|Parameters|Params|Inputs?|Returns?|Outputs?|Yields|Raises|Examples?|Example usage|Notes?|See also|Attributes):\s*", ln, re.I)
        if m:
            out.append(f"\n**{m.group(1)}**\n"); i += 1; continue
        out.append(ln); i += 1
    body = "\n".join(out)
    # keep the author's indentation and line breaks: indented blocks become code
    body = re.sub(r"(?m)^(>>> .*)$", r"    \1", body)
    return body.replace("\n", "  \n").replace("  \n  \n", "\n\n") + "\n"


def member_md(name, node, path, skip_self=False, level=3, prefix=""):
    full = prefix + name
    src = f"{GITHUB}{path.relative_to(ROOT).as_posix()}#L{node.lineno}"
    md = [f"{'#' * level} `{full}`\n", f"```python\n{signature(full, node, skip_self)}\n```\n"]
    rows = args_table(node, skip_self)
    if rows:
        md.append("| input | type | default |\n|---|---|---|\n" + "".join(f"| `{esc_cell(n)}` | {esc_cell(t) or '–'} | {('`' + esc_cell(d) + '`') if d else 'required' if not n.startswith('*') else '–'} |\n" for n, t, d in rows))
    if node.returns is not None:
        md.append(f"**returns** `{esc_cell(ann(node.returns))}`\n")
    md.append(doc_md(ast.get_docstring(node)))
    md.append(f"<sub>[source]({src})</sub>\n")
    return "\n".join(md)


def page(name, path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mdoc = ast.get_docstring(tree)
    allnames = None
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "__all__" for t in n.targets):
            try: allnames = set(ast.literal_eval(n.value))
            except Exception: pass
    public = lambda s: (s in allnames) if allnames else not s.startswith("_")
    funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and public(n.name)]
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and public(n.name)]
    up = "../" * 0
    md = [f"# `{name}`\n", f"[← API index](index.md) · [source]({GITHUB}{path.relative_to(ROOT).as_posix()})\n"]
    if mdoc:
        md.append(doc_md(mdoc))
    # a package __init__ that re-exports names: link each to where it is defined
    if path.name == "__init__.py":
        base = name.split(".")
        reexp = []
        for n in tree.body:
            if isinstance(n, ast.ImportFrom) and n.level >= 1:
                src_mod = ".".join(base[: len(base) - n.level + 1] + ([n.module] if n.module else []))
                names = n.names
                if any(a.name == "*" for a in n.names) and OUT_MODS and src_mod in OUT_MODS:
                    sub = ast.parse(Path(OUT_FILES[src_mod]).read_text(encoding="utf-8"))
                    names = [ast.alias(name=m.name) for m in sub.body
                             if isinstance(m, (ast.FunctionDef, ast.ClassDef)) and not m.name.startswith("_")]
                for a in names:
                    nm = a.asname or a.name
                    if a.name != "*" and public(nm) and (OUT_MODS is None or src_mod in OUT_MODS):
                        reexp.append(f"- [`{name}.{nm}`]({src_mod}.md#{anchor(a.name)}) — from `{src_mod}`")
        if reexp:
            md.append(f"## Available as `{name}.<name>`\n")
            md.extend(reexp); md.append("")
    if classes or funcs:
        md.append("## Contents\n")
        for c in classes:
            meths = [m for m in c.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and (not m.name.startswith("_") or m.name == "__init__")]
            md.append(f"- class [`{c.name}`](#{anchor(c.name)}) — {first_line(ast.get_docstring(c))}")
            for m in meths:
                if m.name != "__init__":
                    md.append(f"  - [`{c.name}.{m.name}`](#{anchor(c.name + m.name)}) — {first_line(ast.get_docstring(m))}")
        for f in funcs:
            md.append(f"- [`{f.name}`](#{anchor(f.name)}) — {first_line(ast.get_docstring(f))}")
        md.append("")
    for c in classes:
        bases = ", ".join(ast.unparse(b) for b in c.bases)
        md.append(f'<a id="{anchor(c.name)}"></a>\n')
        md.append(f"## class `{c.name}`" + (f"({bases})" if bases else "") + "\n")
        init = next((m for m in c.body if isinstance(m, ast.FunctionDef) and m.name == "__init__"), None)
        if init is not None:
            md.append(f"```python\n{signature(c.name, init, True)}\n```\n")
            rows = args_table(init, True)
            if rows:
                md.append("| input | type | default |\n|---|---|---|\n" + "".join(f"| `{esc_cell(n)}` | {esc_cell(t) or '–'} | {('`' + esc_cell(d) + '`') if d else 'required' if not n.startswith('*') else '–'} |\n" for n, t, d in rows))
        md.append(doc_md(ast.get_docstring(c)))
        md.append(f"<sub>[source]({GITHUB}{path.relative_to(ROOT).as_posix()}#L{c.lineno})</sub>\n")
        for m in c.body:
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("_"):
                md.append(f'<a id="{anchor(c.name + m.name)}"></a>\n')
                md.append(member_md(m.name, m, path, skip_self=True, level=3, prefix=c.name + "."))
    for f in funcs:
        md.append(member_md(f.name, f, path))
    return "\n".join(md), mdoc, len(funcs) + sum(1 for c in classes)


OUT_MODS = None
OUT_FILES = {}


def main():
    global OUT_MODS
    global OUT_FILES
    OUT_FILES = dict(modules())
    OUT_MODS = set(OUT_FILES)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("bioscout*.md"):
        try: old.unlink()          # pages of removed modules go; the rest are rewritten
        except OSError: pass
    pages = []
    for name, path in modules():
        try:
            text, mdoc, n = page(name, path)
        except SyntaxError as e:
            print("skipped", name, e); continue
        if n == 0 and not mdoc:
            continue
        (OUT / f"{name}.md").write_text(text, encoding="utf-8")
        pages.append((name, first_line(mdoc), n))
    groups = {}
    for name, summ, n in pages:
        top = ".".join(name.split(".")[:2])
        groups.setdefault(top, []).append((name, summ, n))
    order = [g for g in ORDER if g in groups] + sorted(g for g in groups if g not in ORDER)
    idx = ["# BioScout API reference\n",
           "Every public module, function and class, generated from the docstrings by "
           "`python -m bioscout.devtools.api_docs`. Click a module for its functions; each function shows "
           "its call, its inputs (type, default), what it returns, its docstring and a link to the source.\n",
           "Quick links: " + " · ".join(f"[`{g}`](#{anchor(g)})" for g in order) + "\n"]
    start = ROOT / "docs" / "api_start.md"
    if start.exists():
        idx.append(start.read_text(encoding="utf-8"))
    for g in order:
        idx.append(f"## {g}\n\n| module | what it is | members |\n|---|---|---|")
        for name, summ, n in groups[g]:
            idx.append(f"| [`{name}`]({name}.md) | {esc_cell(summ)[:160]} | {n} |")
        idx.append("")
    (OUT / "index.md").write_text("\n".join(idx), encoding="utf-8")
    print(f"{len(pages)} module pages -> {OUT}")


if __name__ == "__main__":
    main()
