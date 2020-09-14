import subprocess

from qemu_android_test_orchestrator.fsm import WorkerFSM, State, TransitionResult
from qemu_android_test_orchestrator.shared_state import SynchronizedObject


class LogCollector(WorkerFSM):
    @property
    def name(self) -> str:
        return 'Log collector'

    def __init__(self, shared_state: SynchronizedObject) -> None:
        super().__init__(shared_state)
        self.processes = []
        self.files = []

    def run_and_log(self, outfile: str, *command: str):
        f = open(outfile, "w")
        self.files.append(f)
        p = subprocess.Popen(command, stdout=f, stderr=subprocess.STDOUT)
        self.processes.append(p)

    def start_log_collection(self) -> None:
        config = self.shared_state.config
        assert config
        if config['logcat_output']:
            self.run_and_log(config['logcat_output'], 'adb', 'logcat')
            
    def stop_log_collection(self) -> None:
        for p in self.processes:
            p.kill()
        for f in self.files:
            f.flush()
            f.close()

    # noinspection PyBroadException
    async def enter_state(self, state: State) -> TransitionResult:
        if state == State.JOB:
            self.start_log_collection()
            return TransitionResult.DONE
        elif state == State.STOP and self.shared_state.job_proc:
            try:
                self.stop_log_collection()
                return TransitionResult.DONE
            except Exception:
                pass
        return TransitionResult.NOOP

    async def exit_state(self, state: State) -> TransitionResult:
        return TransitionResult.NOOP
