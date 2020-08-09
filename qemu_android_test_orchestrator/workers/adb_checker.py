import asyncio
import warnings

from qemu_android_test_orchestrator.fsm import WorkerFSM, State, TransitionResult


class AdbConnectionChecker(WorkerFSM):
    @property
    def name(self) -> str:
        return 'ADB connection checker'

    async def ensure_adb(self) -> None:
        count = 0
        while count < 120:
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

            await asyncio.sleep(0.5 * self.shared_state.vm_timeout_multiplier)
            count += 1

        raise TimeoutError("Timed out waiting for adb to show up")
    
    async def run_oneshot(self, *cmd):
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.wait()
    
    async def kill_package_verifier(self):
        try:
            await self.run_oneshot('adb', 'shell', 'settings', 'put', 'global', 'package_verifier_enable', '0')
            await self.run_oneshot('adb', 'shell', 'settings', 'put', 'secure', 'package_verifier_enable', '0')
            await self.run_oneshot('adb', 'shell', 'settings', 'put', 'system', 'package_verifier_enable', '0')
        except Exception:
            warnings.warn('Unable to kill Google package verifier, app installation may be blocked later on')

    async def enter_state(self, state: State) -> TransitionResult:
        if state == State.ADB_UP:
            await asyncio.wait_for(self.ensure_adb(), 120 * self.shared_state.vm_timeout_multiplier)
            await asyncio.wait_for(self.kill_package_verifier(), 15 * self.shared_state.vm_timeout_multiplier)
            return TransitionResult.DONE
        return TransitionResult.NOOP

    async def exit_state(self, state: State) -> TransitionResult:
        return TransitionResult.NOOP
