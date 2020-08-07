import asyncio

from qemu_android_test_orchestrator.fsm import WorkerFSM, State, TransitionResult


class JobManager(WorkerFSM):
    @property
    def name(self) -> str:
        return 'Job manager'

    async def run_job(self) -> None:
        assert self.shared_state.config
        try:
            self.shared_state.job_proc = await asyncio.create_subprocess_shell(
                self.shared_state.config['job_command'], cwd=self.shared_state.config['job_workdir']
            )
            await self.shared_state.job_proc.wait()
        finally:
            self.shared_state.job_proc = None

    async def enter_state(self, state: State) -> TransitionResult:
        if state == State.JOB:
            await self.run_job()
            return TransitionResult.DONE
        elif state == State.STOP and self.shared_state.job_proc:
            self.shared_state.job_proc.kill()
            return TransitionResult.DONE
        return TransitionResult.NOOP

    async def exit_state(self, state: State) -> TransitionResult:
        return TransitionResult.NOOP
