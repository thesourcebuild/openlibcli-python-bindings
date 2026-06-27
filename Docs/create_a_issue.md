# Creating a Good Issue

Found a bug or have a feature request? Here's how to write a useful issue.

## Before posting

- Check if a similar issue already exists in the tracker.
- Test with the latest version of `opencli-python`.
- For transport or connection issues (e.g. Telnet, TCP, Serial, Pipe, UNIX socket), verify if the issue is platform-specific (Windows vs. macOS/Linux).
- Try to isolate if the issue is in the Python binding layer (`src/openlibcli/` Python classes/transports) or in the underlying C engine `src/openlibcli_c/`.

## Bug report template

```
### Description
What went wrong?

### Steps to reproduce
1. Minimal Python Code / Script:
   ```python
   # Paste a minimal executable script here
   ```
2. CLI commands entered in the session:
3. Full traceback / output / error message:

### Expected behavior
What should have happened.

### Environment
- OS: (e.g. Windows 11 / Ubuntu 24.04 / macOS)
- Python version: `python --version`
- opencli-python version: (from `openlibcli.__version__` or the `version` file)
- Transport used: (e.g. Telnet, TCP, Serial, Pipe, UNIX socket)

### Attachments (optional)
- Transcripts of the CLI session or debug logs.
```

## Feature request template

```
### Problem
What's missing or inconvenient?

### Proposed solution
How would you like the Python API or the CLI engine to work?

### Alternatives considered
Any other approaches or workarounds you've thought about.
```

## A good issue includes

- A **minimal, executable Python script** reproducing the bug.
- The **full error traceback** or debug logs.
- Your **operating system** and the **transport protocol** being used.
- The **exact CLI command sequence** that triggered the failure.

Well-written issues get fixed faster.

