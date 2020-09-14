import asyncio
import os
import shutil
from typing import Tuple


async def kvm_available() -> Tuple[bool, str]:
    # If libvirt's tool is available it should return a better answer than we can
    if shutil.which('virt-host-validate'):
        p = await asyncio.subprocess.create_subprocess_exec('virt-host-validate', '-q', 'qemu')
        await p.wait()
        return p.returncode == 0, "libvirt"

    # If it's not available, check CPU flags
    if not os.access("/proc/cpuinfo", os.R_OK):
        print(Color.RED + "Unable to read CPU flags" + Color.RESET)
        return False, "cpu flags"
    flaglines = set()
    flags = set()
    with open("/proc/cpuinfo") as f:
        for line in f.readlines():
            if line.startswith('flags:'):
                flaglines.add(line)
    for line in flaglines:
        flags.update(line.split(':')[1].strip().split())

    return 'svm' in flags or 'vmx' in flags, "cpu flags"


class Color:
    BLACK = "\033[0;30m"
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    BROWN = "\033[0;33m"
    BLUE = "\033[0;34m"
    PURPLE = "\033[0;35m"
    CYAN = "\033[0;36m"
    LIGHT_GRAY = "\033[0;37m"
    DARK_GRAY = "\033[1;30m"
    LIGHT_RED = "\033[1;31m"
    LIGHT_GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    LIGHT_BLUE = "\033[1;34m"
    LIGHT_PURPLE = "\033[1;35m"
    LIGHT_CYAN = "\033[1;36m"
    LIGHT_WHITE = "\033[1;37m"
    BOLD = "\033[1m"
    FAINT = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    NEGATIVE = "\033[7m"
    CROSSED = "\033[9m"
    RESET = "\033[0m"
    # cancel SGR codes if we don't write to a terminal
    if not __import__("sys").stdout.isatty():
        for _ in dir():
            if isinstance(_, str) and _[0] != "_":
                locals()[_] = ""
    else:
        # set Windows console in VT mode
        if __import__("platform").system() == "Windows":
            kernel32 = __import__("ctypes").windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            del kernel32
