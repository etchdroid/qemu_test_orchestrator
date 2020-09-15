import asyncio

from qemu_android_test_orchestrator.fsm import WorkerFSM, State, TransitionResult
from qemu_android_test_orchestrator.shared_state import SynchronizedObject
from qemu_android_test_orchestrator.utils import keypress


class PermissionDialogChecker(WorkerFSM):
    ensure_coro = None

    @property
    def name(self) -> str:
        return 'Permission approver'

    def __init__(self, shared_state: SynchronizedObject) -> None:
        super().__init__(shared_state)
        self.should_stop = False

    async def approve_permission(self) -> None:
        # /me *shrugs*
        assert self.shared_state.config
        for key in self.shared_state.config['permission_approve_buttons']:
            await keypress(self.shared_state, key)

    async def ensure_perms_approved(self) -> None:
        # Gradle likes to kill ADB. Wait a little, and restart if dead
        await asyncio.sleep(5)
        self.shared_state.adb_proc = await asyncio.create_subprocess_exec('adb', 'logcat',
                                                                          stdout=asyncio.subprocess.PIPE,
                                                                          stderr=asyncio.subprocess.STDOUT)
        assert self.shared_state.adb_proc.stdout  # so that mypy is happy
        line = await self.shared_state.adb_proc.stdout.readline()
        while line and not self.should_stop:
            if self.shared_state.adb_proc.returncode is not None:
                self.shared_state.adb_proc = await asyncio.create_subprocess_exec('adb', 'logcat',
                                                                                  stdout=asyncio.subprocess.PIPE,
                                                                                  stderr=asyncio.subprocess.STDOUT)
            if b'USB-PERMISSION' in line:
                if b'USB-PERMISSION-REQUESTED' in line:
                    await asyncio.sleep(10)
                    await self.approve_permission()
                # Approve perms only once
                try:
                    self.shared_state.adb_proc.kill()
                except ProcessLookupError:
                    pass
                return
            line = await self.shared_state.adb_proc.stdout.readline()

        await self.shared_state.adb_proc.wait()

    async def enter_state(self, state: State) -> TransitionResult:
        if state == State.JOB:
            self.ensure_coro = asyncio.create_task(self.ensure_perms_approved())
            await self.ensure_coro
            self.ensure_coro = None
            return TransitionResult.DONE
        elif state == State.STOP:
            ret = TransitionResult.NOOP
            self.should_stop = True
            if self.shared_state.adb_proc and self.shared_state.adb_proc.returncode is None:
                try:
                    self.shared_state.adb_proc.kill()
                    ret = TransitionResult.DONE
                except ProcessLookupError:
                    pass
            if self.ensure_coro:
                self.ensure_coro.cancel()
                ret = TransitionResult.DONE
            return ret
        return TransitionResult.NOOP

    async def exit_state(self, state: State) -> TransitionResult:
        return TransitionResult.NOOP
