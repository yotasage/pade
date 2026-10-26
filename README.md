# pade
Python based Analog Design Environment

## Reading simulation results (kymograf)

PADE reads Spectre results with kymograf (a fast PSF reader, built separately) when it is
installed, and with psf_utils otherwise. kymograf is not on PyPI; install its wheel into PADE's
venv:

    pip install kymograf-<version>-cp310-abi3-<platform>.whl

(or `pip install --find-links <folder with the wheel> ".[kymograf]"` from this directory).

kymograf was called fastpsf until 2026-10-26. An installed fastpsf is still used, with a
warning, until you replace it: `pip uninstall fastpsf`, then install the kymograf wheel.

With kymograf:
- `parse()` reads only names, units and sweeps. `Test.evaluate()` reads every signal its
  expressions use in one pass per result file. Memory holds only those signals.
- What to read up front is a choice: `Test(..., load=...)` or `PSFParser.parse(load=...)` takes
  `None` (default: nothing until used), `'all'` (everything, as before), a list of names or
  glob patterns for every analysis (`['vout', 'I0.*']`), or a dict per analysis
  (`{'tran': ['vout', 'time'], 'ac': 'all'}`). `parser.load(...)` reads more later; nothing is
  read twice.
- `test.signals` still works as a dict. Keys, `len` and `in` read nothing; `signals[key]` reads
  that signal; `values()` and `items()` read everything, one pass per file.
- psfbin and psfbinf results are read too. Spectre's output format is the `output_format`
  setting of `Test` and `Spectre`: `'psfbin'` by default when kymograf is installed (smaller and
  faster than psfascii), `'psfascii'` otherwise; `'psfbinf'` is accepted. A `-f`/`-format` in
  `command_options` overrides it.
- If a result file changes after `parse()` (a new simulation into the same directory), reading
  it raises `kymograf.FileChangedError` instead of mixing old and new; parse again.

In both cases, result files are never modified, and psf_utils no longer writes `.cache` files
next to them. Earlier versions rewrote `inf` as `nan` inside `dcOpInfo*` files, which also
renamed anything containing "inf" (`"info"` read as `"nanfo"`); those names are now the true
ones, and an infinite DC value reads as `inf`.
