import asyncio
import os
import random
import shutil
from os.path import exists
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
        if not shared_state.qemu_serial_buffer or b'Detecting Android-x86...' not in shared_state.qemu_serial_buffer:
            await asyncio.sleep(0.5)
        else:
            return True
        count -= 1
    return False


async def wait_shell_prompt(shared_state: SynchronizedObject) -> bool:
    # Send an additional new line to ensure the prompt shows
    shared_state.qemu_serial_writer.write(b'\n')
    await shared_state.qemu_serial_writer.drain()

    count = 200 * shared_state.vm_timeout_multiplier
    while count > 0:
        # Give it an encouragement push every ten times in case it's shy
        if count % 10 == 0:
            shared_state.qemu_serial_writer.write(b'\n')
            await shared_state.qemu_serial_writer.drain()
        # Check the last few bytes for a shell prompt
        if len(shared_state.qemu_serial_buffer) < 15 or b":/ # " not in shared_state.qemu_serial_buffer[:-15]:
            await asyncio.sleep(0.5)
        else:
            return True
        count -= 1
    return False


async def run_and_expect(command: bytes, expect: bytes, within: int, shared_state: SynchronizedObject) -> bool:
    while True:
        shared_state.qemu_serial_writer.write(command)
        await shared_state.qemu_serial_writer.drain()
        await asyncio.sleep(5)
        if expect in shared_state.qemu_serial_buffer[-within:]:
            return True


async def run_and_not_expect(command: bytes, not_expect: bytes, within: int, shared_state: SynchronizedObject,
                             test_times=5) -> bool:
    not_occurrences = 0
    while True:
        shared_state.qemu_serial_writer.write(command)
        await shared_state.qemu_serial_writer.drain()
        await asyncio.sleep(3)
        if not_expect not in shared_state.qemu_serial_buffer[-within:]:
            not_occurrences += 1
        else:
            not_occurrences = 0
        if not_occurrences >= test_times:
            return True


async def wait_shell_available(shared_state: SynchronizedObject) -> None:
    count = 0
    n1, n2 = 0, 0
    while True:
        # Resend challenge every 10 attempts
        if count % 10 == 0:
            n1 = random.randint(0, 0x07FFFFFF)
            n2 = random.randint(0, 0x07FFFFFF)
            shared_state.qemu_serial_writer.write(f'let "n = {n1} + {n2}"; echo $n'.encode())
            await shared_state.qemu_serial_writer.drain()
            await wait_shell_prompt(shared_state)
        if str(n1 + n2).encode() in shared_state.qemu_serial_buffer[-200:]:
            return
        count += 1
        await asyncio.sleep(2)


async def detect_package_manager(shared_state: SynchronizedObject) -> bool:
    return await run_and_expect(b'pm list packages | grep "package.com" | tail -n 5\n', b'package:com', 200,
                                shared_state)


async def wait_exists(file: str):
    count = 30
    while not exists(file):
        count -= 1
        if count == 0:
            raise TimeoutError(f"Timeout waiting for '{file}' to show up")
        await asyncio.sleep(1)


async def keypress(shared_state: SynchronizedObject, key: str) -> None:
    monitor = shared_state.qemu_monitor_writer
    assert monitor
    monitor.write(f'sendkey {key}\n'.encode(errors='replace'))
    await monitor.drain()
    await asyncio.sleep(2)


def balloon_stat() -> None:
    # noinspection PyBroadException
    try:
        with open("/proc/vmstat") as f:
            vmstat = f.read()
        if "balloon" not in vmstat:
            return
        with open("/proc/meminfo") as f:
            meminfo = f.read()

        # Calculate balloon inflation
        balloon_infl = int(
            filter(lambda line: line.startswith("balloon_inflate"), vmstat.splitlines()).__next__().split()[1].strip())
        balloon_defl = int(
            filter(lambda line: line.startswith("balloon_deflate"), vmstat.splitlines()).__next__().split()[1].strip())

        balloon_pages = balloon_infl - balloon_defl

        if balloon_pages == 0:
            print("Memory balloon is not inflated")
            return

        # Calculate approx page size
        mapped_kb_str = filter(lambda line: line.startswith("Mapped:"), meminfo.splitlines()).__next__()
        mapped_bytes = int(mapped_kb_str.split(":")[1].replace("kB", "").strip()) * 1024

        nr_mapped = int(
            filter(lambda line: line.startswith("nr_mapped"), vmstat.splitlines()).__next__().split()[1].strip())
        pagesize = int(round(mapped_bytes / nr_mapped, 0))

        balloon_mbytes = round(balloon_pages * pagesize / 1024 ** 2, 1)

        print(f"Memory balloon inflated to {balloon_pages} pages (approx {balloon_mbytes}MB)")

    except Exception:
        return


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
