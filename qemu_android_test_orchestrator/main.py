import asyncio

from qemu_android_test_orchestrator.config import get_config
from qemu_android_test_orchestrator.fsm import State, ManagerFSM
from qemu_android_test_orchestrator.shared_state import SynchronizedObject
from qemu_android_test_orchestrator.utils import Color
from qemu_android_test_orchestrator.workers.adb_checker import AdbConnectionChecker
from qemu_android_test_orchestrator.workers.job_manager import JobManager
from qemu_android_test_orchestrator.workers.permission_checker import PermissionDialogChecker
from qemu_android_test_orchestrator.workers.qemu_manager import QemuSystemManager
from qemu_android_test_orchestrator.workers.virtwifi_manager import VirtWifiManager
from qemu_android_test_orchestrator.workers.vnc_recorder import VncRecorder
from qemu_android_test_orchestrator.workers.log_collector import LogCollector


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
    if config['vnc_recorder']:
        workers.append(VncRecorder(shared_state))
    if config['logcat_output']:
        workers.append(LogCollector(shared_state))

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

    try:
        for state in transitions:
            loop.run_until_complete(fsm.transition(state))
    except (KeyboardInterrupt, EOFError):
        print(Color.RED + "Shutting down" + Color.RESET)
    finally:
        loop.run_until_complete(asyncio.wait_for(fsm.transition(State.STOP), 30))
        
    if shared_state.job_proc:
        exit(shared_state.job_proc.returncode)
