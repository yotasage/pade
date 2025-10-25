import numpy as np
import numpy.linalg as nla
import os
import sys
from pade import *
from shlib.shlib import to_path, mkdir

def append_dict(d1, d2):
    """
    Append d2 to d1
    """
    for key, value in d2.items():
        # Add key if it does not exist
        if not key in d1:
            d1[key] = value
        # If value is list. append
        elif isinstance(value, list):
            d1[key] += value
        # If value is dict, append
        elif isinstance(value, dict):
            append_dict(d1[key], value)
        # If value is not list or dict, replace existing value
        else:
            d1[key] = value

    return d1

def num2string(val, asint=False, decimals=16, nodot=False):
    # Some special cases
    if isinstance(val, str):
        return val
    elif val is None:
        return None
    if val == 0:
        return '0'
    # Find base and prefix
    exp = 0
    while np.abs(val) < 1:
        val = val * 1000
        exp -= 3
    while np.abs(val) >= 1000:
        val = val / 1000
        exp += 3
    prefix = ''
    if exp == -3:
        prefix = 'm'
    elif exp == -6:
        prefix = 'u'
    elif exp == -9:
        prefix = 'n'
    elif exp == -12:
        prefix = 'p'
    elif exp == -15:
        prefix = 'f'
    elif exp == -18:
        prefix = 'a'
    elif exp == -21:
        prefix = 'z'
    elif exp == -24:
        prefix = 'y'
    elif exp == 3:
        prefix = 'k'
    elif exp == 6:
        prefix = 'M'
    elif exp == 9:
        prefix = 'G'
    elif exp == 12:
        prefix = 'T'
    elif exp == 15:
        prefix = 'P'
    elif exp == 18:
        prefix = 'E'
    elif exp == 21:
        prefix = 'Z'

    # Format
    numstring = ""
    if asint or decimals < 1 or isinstance(val, int):
        numstring = f'{round(val)}' + prefix
    elif nodot:
        val0 = int(np.floor(val))
        val1 = val-val0
        val1 = round(np.ceil(val1*10**(decimals)))
        numstring = f'{val0}{prefix}'
        if val1 != 0:
            if prefix == '':
                numstring += 'x'
            val1str = str(val1)
            while len(val1str) < decimals:
                val1str = '0' + val1str
            numstring += val1str
    else:
        value_str = str(val)
        base_len = len(value_str.split('.')[0])
        precision = base_len + decimals
        width = 0
        numstring = f'{val:{width}.{precision}}' + prefix
    return numstring

def num2nano(val, asint=True, decimals=0, nodot=False):
    """
    Convert a number to nanometers as a string with 'n' as the separator if nodot=True.

    Args:
        val (float or None): value in meters (or base units)
        asint (bool): whether to round to integer
        decimals (int): number of fractional digits if asint=False
        nodot (bool): if True, the 'n' acts as the dot separator

    Returns:
        str: value in nanometers
    """
    if val is None:
        return None

    # Convert to nanometers
    val_nano = val * 1e9

    if asint:
        # Round to integer
        val_str = str(int(round(val_nano)))
        return val_str + 'n'
    
    if nodot:
        val0 = int(val_nano)
        val1 = val_nano - val0
        val1 = round(val1 * 10**decimals)
        val_str = f"{val0}n"  # 'n' acts as the dot
        if val1 != 0:
            val1_str = str(val1)
            while len(val1_str) < decimals:
                val1_str = '0' + val1_str
            val_str += val1_str
        return val_str

    # Normal floating formatting
    val_str = f"{val_nano:.{decimals}f}n"
    return val_str

def string2num(s_val):

    # Find base and prefix
    exp = 0
    prefix = s_val[-1]
    base_val = s_val[:-1]

    if prefix == 'n':
        exp = 1e-9
    elif prefix == 'u':
        exp = 1e-6

    return base_val*exp

# File handling

def file_exist(filename):
    return os.path.exists(filename)

def cat(filename):
    """ Get content of file """

    try:
        with open(filename) as f:
            content = f.read()
        return content
    except FileNotFoundError:
        return None

def writef(lines, filename):
    """ Write lines to file filename """
    with open(filename, "w") as f:
        f.writelines(lines)


# Print results
html_formatter = lambda s: '{:.4f~P}'.format(s)


def get_unit(signal):
    # Hack for noise voltage
    if not signal.units is None:
        signal.units = signal.units.replace('sqrt(Hz)', 'hertz**0.5')
    try:
        unit = getattr(ureg, signal.units)
    except:
        try:
            unit = getattr(ureg, signal.units.lower())
        except:
            unit = None
    return unit




