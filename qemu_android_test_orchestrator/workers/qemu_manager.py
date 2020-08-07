import asyncio

from qemu_android_test_orchestrator.fsm import WorkerFSM, State, TransitionResult


class QemuSystemManager(WorkerFSM):
    @property
    def name(self) -> str:
        return 'QEMU manager'

    async def ensure_qemu(self) -> None:
        assert self.shared_state.config
        self.shared_state.qemu_proc = await asyncio.create_subprocess_exec(
            self.shared_state.config['qemu_bin'],
            *self.shared_state.config['qemu_args'],
            cwd=self.shared_state.config['qemu_workdir'],
            stdin=asyncio.subprocess.PIPE #, stdout=asyncio.subprocess.PIPE
        )
        # I could implement a little checker that runs stuff over serial to see if Android is fully up but it's too
        # much effort for now, this should work for the time being
        await asyncio.sleep(50)

    async def ensure_qemu_stopped(self) -> None:
        if not self.shared_state.qemu_proc or self.shared_state.qemu_proc.returncode:
            return
        # Wait one second before killing QEMU to give time to the other workers to terminate gracefully
        await asyncio.sleep(1)
        self.shared_state.qemu_proc.terminate()
        await asyncio.sleep(0.2)
        if self.shared_state.qemu_proc.returncode is None:
            self.shared_state.qemu_proc.kill()

    async def enter_state(self, state: State) -> TransitionResult:
        if state == State.QEMU_UP:
            await asyncio.wait_for(self.ensure_qemu(), 90)
            return TransitionResult.DONE
        elif state == State.STOP:
            await asyncio.wait_for(self.ensure_qemu_stopped(), 10)
            return TransitionResult.DONE
        return TransitionResult.NOOP

    async def exit_state(self, state: State) -> TransitionResult:
        return TransitionResult.NOOP
