import asyncio

from qemu_android_test_orchestrator.fsm import WorkerFSM, State, TransitionResult


class AdbConnectionChecker(WorkerFSM):
    @property
    def name(self) -> str:
        return 'ADB connection checker'

    async def ensure_adb(self) -> None:
        count = 0
        while count < 10:
            proc = await asyncio.create_subprocess_exec('adb', 'devices', stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.DEVNULL)
            assert proc.stdout
            
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                if line.strip().startswith(b'emulator-') and not line.strip().endswith(b"offline"):
                    return
                
            # Restart adb every 3 attempts
            if count % 3 == 2:
                proc = await asyncio.create_subprocess_exec('adb', 'kill-server')
                await proc.wait()

            await asyncio.sleep(1)
            count += 1

        raise TimeoutError("Timed out waiting for adb to show up")

    async def enter_state(self, state: State) -> TransitionResult:
        if state == State.ADB_UP:
            await asyncio.wait_for(self.ensure_adb(), 60)
            return TransitionResult.DONE
        return TransitionResult.NOOP

    async def exit_state(self, state: State) -> TransitionResult:
        return TransitionResult.NOOP
