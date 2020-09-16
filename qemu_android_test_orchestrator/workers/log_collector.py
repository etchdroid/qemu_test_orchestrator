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

    @staticmethod
    def run_and_log(outfile: str, *command: str):
        with open(outfile, "w") as f:
            p = subprocess.Popen(command, stdout=f, stderr=subprocess.STDOUT)
            p.wait()

    def collect_logs(self) -> None:
        config = self.shared_state.config
        assert config
        if config['logcat_output']:
            self.run_and_log(config['logcat_output'], 'adb', 'logcat', '-d')

    # noinspection PyBroadException
    async def enter_state(self, state: State) -> TransitionResult:
        if state == State.LOGCAT:
            self.collect_logs()
            return TransitionResult.DONE
        return TransitionResult.NOOP

    async def exit_state(self, state: State) -> TransitionResult:
        return TransitionResult.NOOP
