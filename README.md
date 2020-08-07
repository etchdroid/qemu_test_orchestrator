# QEMU Android Test Orchestrator

This is a slightly overkill spaghetti program to set up automated instrumented tests on an emulated Android device on a CI environment.

It addresses the following problems:

- Run with a clean Android-x86 image and bring up "VirtWifi" and ADB
- Run with latest QEMU (the Android emulator doesn't work, and in general it doesn't work for this use-case since the USB stick emulation is broken)
- Be configurable at runtime to some extent
- Try to be somewhat stable and reliable

## Configuration

Default config should be pretty straight-forward, I already spent too much time on this and I don't wanna spend more on documenting it too much. It is
located here: [qemu_android_test_orchestrator/config.py](qemu_android_test_orchestrator/config.py)

It can be overridden by either providing a `config.json` in the `ORCHESTRATOR_CONFIG` environment var, or by setting environment variables which you can
also find in the same file towards the bottom.

Defaults are set up to work with EtchDroid/Libaums.

## How it works (hopefully)

The main idea is that each specific task is handled by a specific worker. For example, bringing up QEMU, connecting to Wi-Fi, checking if ADB is okay,
running the tests.

Each worker is a state machine, and there's a global state machine.

The global state machine tries to go through the following states:

`QEMU_UP`, `NETWORK_UP`, `ADB_UP`, `JOB` (tests)

The global FSM will wait for all workers to reach a certain state before proceeding to the next one. If any worker fails, it will attempt to bring all
of them into the `STOP` state at which they should all shut down.

Each worker will hook itself up to its required states and work independently. This allows specific workers to be added or removed to handle different
quirks required for different Android images, without affecting the others. For example, the hacky `VirtWifiEnabler` worker may not be needed on images
that automatically connect to emulated Ethernet and do not show a fake "VirtWifi" network like Android-x86 9 does.


## Making changes

While this code was written for a particular reason, project and use-case, I can see how it can be used for other projects too. I didn't spend too much
time making sure it's generic enough but it should be quite reusable. Feel free to send patches if you want to add features/fix stuff :)

