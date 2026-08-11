"""Markdown -> PDF, with no LaTeX distribution required.

pandoc's own ``--pdf-engine`` wants TeX (a 4 GB install). This goes
markdown -> .docx (pandoc) -> .pdf (LibreOffice) instead, which is already on
every machine that opens the manuscript, keeps tables and images, and gives a
.docx for free.

    from bioscout.utils.md2pdf import md_to_pdf
    md_to_pdf("review/ceinms_calibration_review.md")

or from the command line::

    bioscout --md2pdf review/ceinms_calibration_review.md
    bioscout --md2pdf docs/*.md --outdir _pdf --toc
"""
from __future__ import annotations

import os
import shutil
import subprocess

__all__ = ["md_to_pdf", "find_pandoc", "find_soffice"]

_PANDOC_CANDIDATES = (
    os.path.join(os.environ.get("CONDA_PREFIX", ""), "Library", "bin", "pandoc.exe"),
    os.path.join(os.environ.get("CONDA_PREFIX", ""), "bin", "pandoc"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Pandoc", "pandoc.exe"),
    r"C:\Program Files\Pandoc\pandoc.exe",
)
_SOFFICE_CANDIDATES = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)


def _first_on_disk(paths):
    return next((p for p in paths if p and os.path.isfile(p)), None)


def find_pandoc():
    """pandoc is often installed but not on PATH. -> path | None"""
    return shutil.which("pandoc") or _first_on_disk(_PANDOC_CANDIDATES)


def _word_to_pdf(docx, pdf):
    """Word's own PDF export, via COM. -> True on success.

    LibreOffice is one more install; Word is already on the machine that is
    editing these documents. Word 17 is wdFormatPDF.
    """
    if os.name != "nt":
        return False
    ps = ("$ErrorActionPreference='Stop';"
          "$w=New-Object -ComObject Word.Application; $w.Visible=$false;"
          f"$d=$w.Documents.Open('{docx}',$false,$true);"
          f"$d.SaveAs([ref]'{pdf}',[ref]17);"
          "$d.Close($false); $w.Quit()")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=300)
    except Exception:
        return False
    return r.returncode == 0 and os.path.isfile(pdf)


def find_soffice():
    """LibreOffice, which does the .docx -> .pdf step. -> path | None"""
    return (shutil.which("soffice") or shutil.which("libreoffice")
            or _first_on_disk(_SOFFICE_CANDIDATES))


def _citeproc_args(pandoc, bibliography=None):
    """--citeproc exists only from pandoc 2.11; older builds need the filter.

    pandoc 2.9 exits with "Unknown option --citeproc", and it auto-invokes the
    pandoc-citeproc filter as soon as --bibliography is passed — so when
    neither is available the bibliography flags have to go too, or the whole
    conversion fails instead of just leaving [@key] literal.
    """
    if not bibliography:
        return []
    try:
        ver = subprocess.run([pandoc, "--version"], capture_output=True,
                             text=True).stdout.split()[1]
        newer = tuple(int(x) for x in ver.split(".")[:2]) >= (2, 11)
    except Exception:
        newer = True
    if newer:
        return ["--citeproc", f"--bibliography={bibliography}"]
    if shutil.which("pandoc-citeproc"):
        return ["--filter", "pandoc-citeproc", f"--bibliography={bibliography}"]
    print("[md2pdf] no citeproc available — [@key] citations stay literal")
    return []


def md_to_pdf(md, out=None, outdir=None, toc=False, bibliography=None,
              csl=None, reference_doc=None, keep_docx=False, quiet=False):
    """Convert one markdown file to PDF. -> path to the .pdf, or None.

    ``out``            explicit output path; otherwise <md stem>.pdf
    ``outdir``         write beside the source unless given
    ``toc``            prepend a table of contents
    ``bibliography``   .bib to resolve [@key] citations against
    ``csl``            citation style file
    ``reference_doc``  .docx whose styles the output should adopt
    ``keep_docx``      keep the intermediate .docx instead of deleting it

    Images are resolved relative to the markdown file, so a document written to
    be read in place converts without editing its paths.
    """
    md = os.path.abspath(md)
    if not os.path.isfile(md):
        raise FileNotFoundError(md)
    pandoc, soffice = find_pandoc(), find_soffice()
    if not pandoc:
        print("[md2pdf] pandoc not found. conda install -c conda-forge pandoc")
        return None
    # Word is tried when LibreOffice is absent; only if BOTH are missing is
    # there nothing that can turn the .docx into a .pdf.
    if not soffice and os.name != "nt":
        print("[md2pdf] LibreOffice not found — needed for the .docx -> .pdf "
              "step. https://www.libreoffice.org/download/")
        return None

    src_dir = os.path.dirname(md)
    dest_dir = os.path.abspath(outdir or (os.path.dirname(out) if out else src_dir))
    os.makedirs(dest_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(out or md))[0]
    docx = os.path.join(dest_dir, stem + ".docx")

    args = [pandoc, os.path.basename(md), "--resource-path=.", "-o", docx]
    args += _citeproc_args(pandoc, bibliography)
    if csl:
        args.append(f"--csl={csl}")
    if toc:
        args += ["--toc", "--toc-depth=3"]
    if reference_doc:
        args.append(f"--reference-doc={reference_doc}")
    # cwd is the markdown's own folder so relative image paths resolve
    r = subprocess.run(args, cwd=src_dir or ".", capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(docx):
        print(f"[md2pdf] pandoc failed: {r.stderr.strip().splitlines()[-1:] or ''}")
        return None

    pdf = os.path.join(dest_dir, stem + ".pdf")
    ok = False
    if soffice:
        r = subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                            "--outdir", dest_dir, docx],
                           capture_output=True, text=True)
        ok = r.returncode == 0 and os.path.isfile(pdf)
    if not ok:
        ok = _word_to_pdf(docx, pdf)
    if not ok:
        print("[md2pdf] no .pdf — neither LibreOffice nor Word could convert "
              f"{os.path.basename(docx)}. The .docx is written; 'Save as PDF' "
              "from Word, or install LibreOffice.")
        return None
    if out and os.path.abspath(out) != pdf:
        shutil.move(pdf, out)
        pdf = os.path.abspath(out)
    if not keep_docx:
        try:
            os.remove(docx)
        except OSError:
            pass
    if not quiet:
        print(f"[md2pdf] -> {pdf}")
    return pdf


def md_to_pdf_many(paths, **kw):
    """Convert several files. -> [path, ...] of the PDFs actually written."""
    return [p for p in (md_to_pdf(m, **kw) for m in paths) if p]
