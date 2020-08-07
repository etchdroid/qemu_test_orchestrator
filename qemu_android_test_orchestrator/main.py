import asyncio
import os
import sys

from qemu_android_test_orchestrator.config import get_config
from qemu_android_test_orchestrator.fsm import State, ManagerFSM
from qemu_android_test_orchestrator.shared_state import SynchronizedObject
from qemu_android_test_orchestrator.workers.adb_checker import AdbConnectionChecker
from qemu_android_test_orchestrator.workers.job_manager import JobManager
from qemu_android_test_orchestrator.workers.virtwifi_manager import VirtWifiManager
from qemu_android_test_orchestrator.workers.permission_checker import PermissionDialogChecker
from qemu_android_test_orchestrator.workers.qemu_manager import QemuSystemManager


def main() -> None:
    config = get_config()
    shared_state = SynchronizedObject()
    shared_state.config = config

    workers = [
        QemuSystemManager(shared_state),
        JobManager(shared_state),
        AdbConnectionChecker(shared_state)
    ]

    if config['virtwifi_hack']:
        workers.append(VirtWifiManager(shared_state))
    if config['permission_approve']:
        workers.append(PermissionDialogChecker(shared_state))

    transitions = (
        State.QEMU_UP,
        State.NETWORK_UP,
        State.ADB_UP,
        State.JOB
    )

    fsm = ManagerFSM()
    for w in workers:
        fsm.register_worker(w)

    loop = asyncio.get_event_loop()

    print("Running with enabled worker:", ', '.join(map(lambda x: f"'{x.name}'", workers)))
    if not os.isatty(sys.stdout.fileno()):
        print("Progress is reported as workers finish processing")

    try:
        for state in transitions:
            loop.run_until_complete(fsm.transition(state))
    except (KeyboardInterrupt, EOFError):
        print("Shutting down")
    finally:
        loop.run_until_complete(fsm.transition(State.STOP))
