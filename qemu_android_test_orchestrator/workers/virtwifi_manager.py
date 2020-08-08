import asyncio
import base64
import os
from typing import cast

from qemu_android_test_orchestrator.fsm import WorkerFSM, State, TransitionResult


class VirtWifiManager(WorkerFSM):
    @property
    def name(self) -> str:
        return 'VirtWifi enabler'

    async def ensure_virtwifi(self) -> None:
        assert self.shared_state.config
        apk_file = self.shared_state.config['virtwificonnector_apk']
        if not os.access(apk_file, os.R_OK):
            raise OSError(f"VirtWifiConnector APK path '{apk_file}' does not exist or is inaccessible")
        with open(apk_file, 'rb') as f:
            apk_b64 = base64.standard_b64encode(f.read())

        qemu_proc = self.shared_state.qemu_proc
        assert qemu_proc and qemu_proc.stdin

        # Turn on wi-fi
        qemu_proc.stdin.write(b'svc wifi enable\n')
        await qemu_proc.stdin.drain()
        await asyncio.sleep(3)

        # Send app apk
        qemu_proc.stdin.write(b'base64 -d > /data/local/tmp/app.apk << EOF\n')
        # Send the base64 string in 1KB chunks casuse Python and Busybox are little cry babies
        chunk_size = 1024
        for i in range(0, len(apk_b64), chunk_size):
            qemu_proc.stdin.write(apk_b64[i:i+chunk_size] + b'\n')
            await qemu_proc.stdin.drain()
        await asyncio.sleep(0.5)
        qemu_proc.stdin.write(b'EOF\n')
        await qemu_proc.stdin.drain()
        await asyncio.sleep(3)

        # Install app
        qemu_proc.stdin.write(b'pm install /data/local/tmp/app.apk\n')
        await qemu_proc.stdin.drain()
        await asyncio.sleep(1)

        # We like our RAM
        qemu_proc.stdin.write(b'rm /data/local/tmp/app.apk\n')
        await qemu_proc.stdin.drain()

        # Open app
        qemu_proc.stdin.write(b'am start-activity -a android.intent.action.MAIN -n '
                              b'eu.depau.virtwificonnector/.MainActivity\n')
        await qemu_proc.stdin.drain()
        await asyncio.sleep(2)

        # Dismiss "old API" warning
        qemu_proc.stdin.write(b'input keyevent KEYCODE_ESCAPE\n')
        await qemu_proc.stdin.drain()
        await asyncio.sleep(0.5)

    async def enter_state(self, state: State) -> TransitionResult:
        if state == State.NETWORK_UP:
            await asyncio.wait_for(self.ensure_virtwifi(), 99999)
            return TransitionResult.DONE
        return TransitionResult.NOOP

    async def exit_state(self, state: State) -> TransitionResult:
        return TransitionResult.NOOP
