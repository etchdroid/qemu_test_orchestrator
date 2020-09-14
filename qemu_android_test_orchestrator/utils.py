import asyncio
import os
import shutil
from typing import Tuple

from qemu_android_test_orchestrator.shared_state import SynchronizedObject


async def kvm_available() -> Tuple[bool, str]:
    # If libvirt's tool is available it should return a better answer than we can
    if shutil.which('virt-host-validate'):
        p = await asyncio.subprocess.create_subprocess_exec('virt-host-validate', '-q', 'qemu',
                                                            stdout=asyncio.subprocess.PIPE)
        stdout = await p.stdout.read()
        await p.wait()
        return b"FAIL" not in stdout, "libvirt"

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


async def wait_kms(shared_state: SynchronizedObject) -> bool:
    count = 1000 * shared_state.vm_timeout_multiplier
    while count > 0:
        if not shared_state.qemu_sock_buffer or b'Detecting Android-x86... found at' not in shared_state.qemu_sock_buffer:
            await asyncio.sleep(0.5)
        else:
            return True
        count -= 1
    return False


async def wait_shell_prompt(shared_state: SynchronizedObject) -> bool:
    # Send an additional new line to ensure the prompt shows
    shared_state.qemu_sock_writer.write(b'\n')
    await shared_state.qemu_sock_writer.drain()

    count = 200 * shared_state.vm_timeout_multiplier
    while count > 0:
        # Give it an encouragement push every ten times in case it's shy
        if count % 10 == 0:
            shared_state.qemu_sock_writer.write(b'\n')
            await shared_state.qemu_sock_writer.drain()
        # Check the last few bytes for a shell prompt
        if len(shared_state.qemu_sock_buffer) < 15 or b":/ # " not in shared_state.qemu_sock_buffer[:-15]:
            await asyncio.sleep(0.5)
        else:
            return True
        count -= 1
    return False


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
