from pade import *
from pade.signal import Signal
from pade.utils import get_unit
from shlib import ls, to_path, mkdir, rm
from collections.abc import MutableMapping
from fnmatch import fnmatchcase
from numbers import Number
from typing import Any, List, Mapping, Union
import pandas as pd
import numpy as np
import os
import re
import shutil
import tempfile

# fastpsf reads psfascii, psfbin and psfbinf lazily and selectively. Without it, psf_utils
# reads psfascii only, and every signal is loaded by parse(). A fastpsf too old for PADE
# (without PSF.load) counts as not installed.
try:
    from fastpsf.compat import PSF, Quantity
    if not hasattr(PSF, 'load'):
        warn('The installed fastpsf is too old for PADE (no PSF.load): reading results with psf_utils. Install a newer fastpsf wheel')
        raise ImportError('fastpsf too old')
    HAVE_FASTPSF = True
except ImportError:
    from psf_utils import PSF, Quantity
    HAVE_FASTPSF = False


class _Pending:
    """A signal that is listed but not read yet"""
    __slots__ = ('result', 'name', 'analysis', 'sweep')

    def __init__(self, result, name, analysis, sweep):
        self.result = result
        self.name = name
        self.analysis = analysis
        self.sweep = sweep


class SignalDict(MutableMapping):
    """
    Dictionary of signals that reads values on first access.
    Keys are listed without reading anything. values(), items() and the parser's
    get_signal_list() and get_dataframe() read what they need in one pass per result file.
    """
    def __init__(self, parser):
        self._parser = parser
        self._d = {}

    def __getitem__(self, key):
        v = self._d[key]
        if isinstance(v, _Pending):
            self._parser._load_keys([key])
            v = self._d[key]
        return v

    def __setitem__(self, key, value):
        self._d[key] = value

    def __delitem__(self, key):
        del self._d[key]

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __contains__(self, key):
        return key in self._d

    def __repr__(self):
        loaded = sum(1 for v in self._d.values() if not isinstance(v, _Pending))
        return f'SignalDict({len(self._d)} signals, {loaded} loaded)'

    def values(self):
        self._parser._load_keys(list(self._d))
        return self._d.values()

    def items(self):
        self._parser._load_keys(list(self._d))
        return self._d.items()

    def is_loaded(self, key):
        return not isinstance(self._d[key], _Pending)

    def _entry(self, key):
        """The Signal or _Pending of a key, without reading it. Both have name, analysis and sweep"""
        return self._d[key]


class PSFParser(object):
    """
    Helper class for parsing PSF result files (psfascii, and with fastpsf psfbin and psfbinf).

    With fastpsf installed, parse() reads only the declarations of each result file (names,
    units, sweeps), and signal values are read when first used, or all at once by load().
    Result files are never modified.
    """
    def __init__(self, output_dir, sim_name, **kwargs):
        """
        """
        self.output_dir = output_dir
        self.sim_name = sim_name
        # Dictionary for holding signals
        # self.signals = {'sim_name:analysis:name': Signal()}
        self.signals = SignalDict(self)
        self.meta = {}

    def parse(self, load=None):
        """
        Parse psf file into traces

        Parameters:
            load: None, 'all', list or dict
                Signals to read now, in one pass per result file:
                None (default) reads no values until they are used;
                'all' reads everything (as before fastpsf);
                a list of names or glob patterns, e.g. ['vout', 'I0.*'], applies to every analysis;
                a dict chooses per analysis, e.g. {'tran': ['vout', 'time'], 'ac': 'all'}.
                More can be read later with load().
                Without fastpsf every signal is read regardless.
        """
        raw_files = ls(self.output_dir)

        for file in raw_files:
            filename = file.name
            # Only parse valid analysis files
            if not self.is_valid_analysis(filename):
                continue
            analysis_name = filename.split('.')[0]
            display(f'PARSING PSF FILE: {filename} ({self.sim_name})')

            if HAVE_FASTPSF:
                self._open(file, analysis_name)
            else:
                self._parse_psf_utils(file, analysis_name)

        if load is not None:
            self.load(load)

    def _open(self, file, analysis_name):
        """List the signals of a file; values are read on first use"""
        # Parsing might fail
        try:
            psf = PSF(file, signals=[])
            self.meta = psf.meta
        except Exception as err:
            warn(f'Could not parse file {file}, error occurred: {err}')
            return
        for name in psf.signals:
            self.signals[f'{self.sim_name}:{analysis_name}:{name}'] = _Pending(psf, name, analysis_name, False)
        if psf.sweeps:
            for sweep in psf.sweeps:
                self.signals[f'{self.sim_name}:{analysis_name}:{sweep.name}'] = _Pending(psf, sweep.name, analysis_name, True)

    def _parse_psf_utils(self, file, analysis_name):
        """Without fastpsf: read everything with psf_utils"""
        if _is_binary(file):
            warn(f'Could not parse file {file}: it is not psfascii. Install fastpsf to read psfbin results')
            return
        try:
            # Read a cache psf_utils wrote earlier, but write nothing next to the result file
            psf = PSF(file, update_cache=False)
        except Exception as err:
            # Older psf_utils grammars fail on `inf`: retry on a corrected copy, never on the result file
            if 'dcOpInfo' not in file.name:
                warn(f'Could not parse file {file}, error occurred: {err}')
                return
            try:
                psf = _parse_inf_as_nan(file)
            except Exception as err:
                warn(f'Could not parse file {file}, error occurred: {err}')
                return
        self.meta = psf.meta
        for signal in psf.all_signals():
            s = _signal(signal, analysis_name, self.sim_name)
            self.signals[f'{self.sim_name}:{analysis_name}:{s.name}'] = s
        if psf.sweeps:
            for sweep in psf.sweeps:
                s = _sweep_signal(sweep, analysis_name, self.sim_name)
                self.signals[f'{self.sim_name}:{analysis_name}:{s.name}'] = s

    def load(self, signals: Union[str, List[str], Mapping[Any, Union[str, List[str]]]] = 'all', missing_ok: bool = False):
        """
        Read signal values now, in one pass per result file. Signals already read are not read again.

        Parameters:
            signals: 'all', list or dict
                As parse(load=...): 'all', a list of names or glob patterns for every analysis,
                or a dict {analysis: list or 'all'}
            missing_ok: bool
                If False, warn about names and patterns that match nothing
        """
        if isinstance(signals, Mapping):
            wanted = signals
        else:
            wanted = {None: signals}
        keys = []
        for analysis, names in wanted.items():
            in_analysis = [k for k in self.signals if analysis is None or self.signals._entry(k).analysis == analysis]
            if names == 'all':
                keys += in_analysis
                continue
            if isinstance(names, str):
                names = [names]
            by_name = {}
            for k in in_analysis:
                by_name.setdefault(self.signals._entry(k).name, []).append(k)
            for pattern in names:
                if pattern in by_name:
                    hits = by_name[pattern]
                elif any(c in pattern for c in '*?['):
                    hits = [k for n, ks in by_name.items() if fnmatchcase(n, pattern) for k in ks]
                else:
                    hits = []
                if not hits and not missing_ok:
                    where = f' in analysis {analysis}' if analysis is not None else ''
                    warn(f'Signal {pattern} not available{where}, not loaded')
                keys += hits
        self._load_keys(keys)

    def _load_keys(self, keys):
        """Read the pending signals among keys: one pass per result file"""
        pending = {}
        for k in dict.fromkeys(keys):
            v = self.signals._d.get(k)
            if isinstance(v, _Pending):
                pending.setdefault(id(v.result), []).append((k, v))
        for entries in pending.values():
            psf = entries[0][1].result
            psf.load([v.name for _, v in entries if not v.sweep])
            for k, v in entries:
                if v.sweep:
                    s = _sweep_signal(psf.get_sweep(), v.analysis, self.sim_name)
                else:
                    s = _signal(psf.get_signal(v.name), v.analysis, self.sim_name)
                self.signals._d[k] = s

    def is_valid_analysis(self, filename):
        """
        Check if analysis (filename) is a valid result file
        """
        res = True
        valid_types = ['tran', 'ac', 'dc', 'info', 'stb', 'noise', 'pss', 'pnoise']
        # logFile etc..
        if len(filename.split('.')) < 2:
            res = False
        elif 'margin.stb' in filename:
            res = False # stb.margin not supported
        else:
            t = filename.split('.')[-1]
            res = t in valid_types
        return res

    def get_signals_from_same_sim(self, name_list, analysis):
        self.load({analysis: name_list}, missing_ok=True)
        signals = []
        for name in name_list:
            signals.append(self.get_signal(name, analysis))
        return signals


    def get_signal(self, name, analysis):
        identifier = f'{self.sim_name}:{analysis}:{name}'
        if identifier in self.signals:
            return self.signals[identifier]
        else:
            warn(f'Signal {name} from analysis {analysis} not available. Returning NaN')
            return np.nan

    def get_signal_list(self, sig_name_regex, analysis):
        identifier = f'{sig_name_regex}'
        names = [name for name in self.signals if not re.search(identifier, name) is None]
        self._load_keys(names)
        return [self.signals[name] for name in names]


    def add_signal(self, signal):
        if isinstance(signal, Signal):
            identifier = f'{signal.simulation}:{signal.analysis}:{signal.name}'
            if identifier in self.signals:
                error(f'Signal {identifier} not added because it already exist')
            else:
                self.signals[identifier] = signal
                info(f'Added signal {identifier}')
        else:
            error(f'Signal not added because it is not a Signal object')

    def get_dataframe(self, analysis):
        """
        Return all data from given analysis as dataframe
        """
        identifiers = [identifier for identifier in self.signals if analysis in identifier]
        self._load_keys(identifiers)
        df_dict = {}
        for identifier in identifiers:
            df_dict[identifier.replace(analysis + ':', '')] = self.signals[identifier].trace
        return pd.DataFrame(df_dict)

    def get_sweep(self, analysis):
        for key in self.signals:
            entry = self.signals._entry(key)
            if entry.analysis == analysis and entry.sweep:
                return self.signals[key]


def _signal(signal, analysis_name, sim_name):
    """Wrap a PSF signal in a pade Signal"""
    if isinstance(signal.ordinate, Quantity):
        trace = np.array([signal.ordinate.real + 1j*signal.ordinate.imag])
    else:
        trace = signal.ordinate

    unit = get_unit(signal)
    q = ureg.Quantity(trace, unit)
    return Signal(trace, q.units, name=signal.name, analysis=analysis_name, simulation=sim_name, sweep=False)


def _sweep_signal(sweep, analysis_name, sim_name):
    """Wrap a PSF sweep in a pade Signal"""
    try:
        unit = getattr(ureg, sweep.units)
    except:
        unit = ''
    return Signal(sweep.abscissa, unit, name=sweep.name, analysis=analysis_name, simulation=sim_name, sweep=True)


def _is_binary(file):
    """psfascii files start with HEADER"""
    with open(file, 'rb') as f:
        return f.read(6) != b'HEADER'


def _parse_inf_as_nan(file):
    """
    Parse a copy of file with psf_utils, with the value tokens `inf` replaced by `nan`.
    The copy is written to a temporary directory and deleted; the result file is not touched.
    Quoted strings (names, units, header values) are kept as they are.
    """
    token = re.compile(r'(?<![\w.])([+-]?)inf(?![\w.])')
    tmpdir = tempfile.mkdtemp(prefix='pade-psf-')
    try:
        tmp = os.path.join(tmpdir, file.name)
        with open(file, 'r') as src, open(tmp, 'w') as dst:
            for line in src:
                parts = line.split('"')
                # Even parts are outside quotes
                for i in range(0, len(parts), 2):
                    parts[i] = token.sub('nan', parts[i])
                dst.write('"'.join(parts))
        return PSF(tmp, use_cache=False, update_cache=False)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
