import asyncio

from qemu_android_test_orchestrator.fsm import WorkerFSM, State, TransitionResult
from qemu_android_test_orchestrator.utils import kvm_available, Color, wait_shell_prompt


class QemuSystemManager(WorkerFSM):
    @property
    def name(self) -> str:
        return 'QEMU manager'

    async def qemu_log_reader(self):
        reader = self.shared_state.qemu_sock_reader

        while not self.shared_state.qemu_sock_stopdebug:
            line = await reader.readline()
            self.shared_state.qemu_sock_buffer += line
            if self.shared_state.config['qemu_debug']:
                print(Color.YELLOW + "VM:" + Color.RESET, line.decode(errors="replace"), end='')

    async def ensure_qemu(self) -> None:
        assert self.shared_state.config

        qemu_debug = self.shared_state.config['qemu_debug']
        qemu_args = list(self.shared_state.config['qemu_args'])
        kvm, decider = await kvm_available()
        if kvm:
            if '-enable-kvm' not in qemu_args:
                qemu_args.insert(0, '-enable-kvm')
            print(Color.GREEN + f"KVM is available (decider: {decider})" + Color.RESET)
        else:
            # Make all timeouts 5 times longer
            self.shared_state.vm_timeout_multiplier = 5
            if '-enable-kvm' in qemu_args:
                qemu_args.remove('-enable-kvm')
            print(Color.RED + f"KVM is not available, performance may be very low (decider: {decider})" + Color.RESET)

        if qemu_debug:
            print(Color.YELLOW + "QEMU args:" + Color.RESET, " ".join(qemu_args))

        self.shared_state.qemu_proc = await asyncio.create_subprocess_exec(
            self.shared_state.config['qemu_bin'],
            *qemu_args,
            cwd=self.shared_state.config['qemu_workdir'],
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL
        )

        # Create serial console socket handle pairs
        await asyncio.sleep(1)
        reader, writer = asyncio.open_unix_connection("/tmp/qemu-android.sock")
        self.shared_state.qemu_sock_reader = reader
        self.shared_state.qemu_sock_writer = writer
        self.shared_state.qemu_sock_buffer = ""
        self.shared_state.qemu_sock_stopdebug = False
        asyncio.create_task(self.qemu_log_reader())

        # Wait for a root shell to show up over serial
        found = await wait_shell_prompt(self.shared_state)
        if not found:
            print(Color.RED + "Warning: timeout while waiting for shell prompt" + Color.RESET)

        # Give it some other time to start zygote and all the bloat
        await asyncio.sleep(10 * self.shared_state.vm_timeout_multiplier)

    async def ensure_qemu_stopped(self) -> None:
        if not self.shared_state.qemu_proc or self.shared_state.qemu_proc.returncode:
            return
        self.shared_state.qemu_sock_stopdebug = True
        # Wait one second before killing QEMU to give time to the other workers to terminate gracefully
        await asyncio.sleep(1)
        self.shared_state.qemu_sock_writer.close()
        try:
            self.shared_state.qemu_proc.terminate()
        except ProcessLookupError:
            return
        await asyncio.sleep(0.2)
        if self.shared_state.qemu_proc.returncode is None:
            try:
                self.shared_state.qemu_proc.kill()
            except ProcessLookupError:
                pass

    async def enter_state(self, state: State) -> TransitionResult:
        if state == State.QEMU_UP:
            await asyncio.wait_for(self.ensure_qemu(), 300 * self.shared_state.vm_timeout_multiplier)
            return TransitionResult.DONE
        elif state == State.STOP:
            await asyncio.wait_for(self.ensure_qemu_stopped(), 10)
            return TransitionResult.DONE
        return TransitionResult.NOOP

    async def exit_state(self, state: State) -> TransitionResult:
        return TransitionResult.NOOP
