# `bioscout.devtools.md2pdf`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/md2pdf.py)

Markdown -> PDF, with no LaTeX distribution required.

pandoc's own ``--pdf-engine`` wants TeX (a 4 GB install). This goes  
markdown -> .docx (pandoc) -> .pdf (LibreOffice) instead, which is already on  
every machine that opens the manuscript, keeps tables and images, and gives a  
.docx for free.

    from bioscout.devtools.md2pdf import md_to_pdf  
    md_to_pdf("review/ceinms_calibration_review.md")

or from the command line::

    bioscout --md2pdf review/ceinms_calibration_review.md  
    bioscout --md2pdf docs/*.md --outdir _pdf --toc

## Contents

- [`find_pandoc`](#find_pandoc) — pandoc is often installed but not on PATH. -> path | None
- [`find_soffice`](#find_soffice) — LibreOffice, which does the .docx -> .pdf step. -> path | None
- [`md_to_pdf`](#md_to_pdf) — Convert one markdown file to PDF. -> path to the .pdf, or None.

### `find_pandoc`

```python
find_pandoc()
```

pandoc is often installed but not on PATH. -> path | None

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/md2pdf.py#L41)</sub>

### `find_soffice`

```python
find_soffice()
```

LibreOffice, which does the .docx -> .pdf step. -> path | None

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/md2pdf.py#L67)</sub>

### `md_to_pdf`

```python
md_to_pdf(
    md,
    out=None,
    outdir=None,
    toc=False,
    bibliography=None,
    csl=None,
    reference_doc=None,
    keep_docx=False,
    quiet=False
)
```

| input | type | default |
|---|---|---|
| `md` | – | required |
| `out` | – | `None` |
| `outdir` | – | `None` |
| `toc` | – | `False` |
| `bibliography` | – | `None` |
| `csl` | – | `None` |
| `reference_doc` | – | `None` |
| `keep_docx` | – | `False` |
| `quiet` | – | `False` |

Convert one markdown file to PDF. -> path to the .pdf, or None.

``out``            explicit output path; otherwise <md stem>.pdf  
``outdir``         write beside the source unless given  
``toc``            prepend a table of contents  
``bibliography``   .bib to resolve [@key] citations against  
``csl``            citation style file  
``reference_doc``  .docx whose styles the output should adopt  
``keep_docx``      keep the intermediate .docx instead of deleting it

Images are resolved relative to the markdown file, so a document written to  
be read in place converts without editing its paths.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/md2pdf.py#L97)</sub>
