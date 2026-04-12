# Pinned public evidence excerpt: `examples/openclaw-plugin/INSTALL-ZH.md` lines 241-367

- Upstream repo: `https://github.com/volcengine/OpenViking`
- Immutable blob URL: `https://github.com/volcengine/OpenViking/blob/f6a4b4e/examples/openclaw-plugin/INSTALL-ZH.md#L241-L367`
- Capture purpose: freeze the current public OpenClaw context-engine installation path.

## Facts recorded from the pinned page

1. The document explicitly describes the **new** OpenViking plugin built on the `context-engine` architecture.
2. It says the new `openviking` plugin is **incompatible** with the old `memory-openviking` plugin and that they must not be mixed.
3. It documents current prerequisites including `OpenClaw >= 2026.3.7` and `Node.js >= 22`.
4. It shows plugin configuration under `plugins.entries.openviking.config`.
5. It places local-mode server settings such as VLM / embedding / `server.port` in `ov.conf`.
6. It uses `plugins.slots.contextEngine` to validate whether `openviking` has taken over the context-engine slot.
7. It points users to OpenClaw logs and OpenViking logs for runtime verification.
