# Example workspace

This folder is a **sample** kAIju workspace shipped with the repository so you can
try the CLI and the GUI without creating cards first. It is not live work.

From the repository root, after `uv tool install --editable ./src`:

```bash
kaiju gui examples
kaiju -C examples search "" --open
kaiju -C examples guide
```

Local rule for this sample: keep attachments inside the card folder (see `MT-0001/sql/`).
