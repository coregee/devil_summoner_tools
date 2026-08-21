# Translation editor

The root `tools` package contains local, repository-aware developer tools. Its
first application is the translation editor:

```powershell
python -B -m tools.editor
```

The editor binds only to `127.0.0.1`, opens the canonical text assets under
`assets/text`, traces their Saturn consumer bindings, and validates proposed
translations before saving them. Known hard validation failures block writes.
Unknown surface measurements remain visible without being treated as success.

Generated Saturn font binaries and metrics under `saturn/font/generated/game`
enable exact-font previews. If those artifacts are absent, corpus editing still
works and the affected measurements are reported as unavailable.

Use `--no-browser` to start the server without opening a browser, or `--port`
to select another loopback port.

