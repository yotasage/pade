# pade
Python based Analog Design Environment

## Reading simulation results (kymograf)

PADE reads Spectre results with kymograf (a fast PSF reader, built separately) when it is
installed, and with psf_utils otherwise. kymograf is not on PyPI; install its wheel into PADE's
venv:

    pip install kymograf-<version>-cp310-abi3-<platform>.whl

(or `pip install --find-links <folder with the wheel> ".[kymograf]"` from this directory).

kymograf was called fastpsf until 2026-10-26. PADE no longer uses an installed fastpsf: run
`pip uninstall fastpsf`, then install the kymograf wheel (without it, PADE reads with psf_utils).

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
- `'nutbin'` and `'nutascii'` are accepted too. Spectre writes them as one file, not a folder,
  so PADE passes `-raw simulation_output/output.raw` for them (Spectre stops with CMI-2011,
  "Unable to open the raw file", if `-raw` names a folder). PSFParser does not read them: the
  simulation runs and parsing is skipped with a warning.
- A `-raw PATH` in `command_options` wins over PADE's, for every format: PATH is used as given,
  the full path. PSF results are then parsed from PATH.
- The cache (`run(cache=True)`) skips a simulation only if the netlist is unchanged and its last
  run finished with the same format and `-raw` (`netlists/<corner>.run` records them). A run that
  failed or was stopped is never taken for a cached result.
- If a result file changes after `parse()` (a new simulation into the same directory), reading
  it raises `kymograf.FileChangedError` instead of mixing old and new; parse again.

In both cases, result files are never modified, and psf_utils no longer writes `.cache` files
next to them. Earlier versions rewrote `inf` as `nan` inside `dcOpInfo*` files, which also
renamed anything containing "inf" (`"info"` read as `"nanfo"`); those names are now the true
ones, and an infinite DC value reads as `inf`.
