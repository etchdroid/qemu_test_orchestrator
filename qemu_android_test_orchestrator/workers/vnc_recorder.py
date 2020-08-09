import asyncio

from qemu_android_test_orchestrator.fsm import WorkerFSM, State, TransitionResult


class VncRecorder(WorkerFSM):
    ensure_coro = None

    @property
    def name(self) -> str:
        return 'VNC recorder'

    async def ensure_vnc_recorder(self) -> None:
        await asyncio.sleep(1)  # Wait a second for QEMU to start
        recorder_bin = self.shared_state.config['vnc_recorder_bin'] or 'vnc_recorder'
        self.shared_state.vnc_recorder_proc = \
            await asyncio.create_subprocess_exec(recorder_bin, '--password', '', '--port',
                                                 str(self.shared_state.config['vnc_recorder_port']))

    async def enter_state(self, state: State) -> TransitionResult:
        if state == State.QEMU_UP:
            await asyncio.wait_for(self.ensure_vnc_recorder(), 10)
            return TransitionResult.DONE
        elif state == State.STOP:
            if self.shared_state.vnc_recorder_proc and self.shared_state.vnc_recorder_proc.returncode is None:
                try:
                    self.shared_state.vnc_recorder_proc.terminate()
                    return TransitionResult.DONE
                except ProcessLookupError:
                    pass
        return TransitionResult.NOOP

    async def exit_state(self, state: State) -> TransitionResult:
        return TransitionResult.NOOP
