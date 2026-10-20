# Contributing to BlindChess

Thank you for contributing to BlindChess. This project is built on the philosophy of local-first, privacy-respecting, distraction-free chess improvement.

## Guiding Principles

1. **Local-First & Offline**: BlindChess must never require internet access during normal operation. No telemetry, cloud APIs, accounts, or background network requests.
2. **Authoritative Chess Rules**: All moves, positions, and game states must be validated using authoritative chess rules.
3. **No Fabricated Evaluations**: Engine evaluations must come directly from verified UCI engine processes.
4. **Resilient Terminal Experience**: Interfaces must work over standard Linux terminals and SSH, with both Unicode and pure ASCII support.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/your-username/blindchess.git
cd blindchess

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies and test tools
pip install -e ".[dev]"

# Run tests
pytest
```

## Submitting Pull Requests

- Keep commits focused and well-documented.
- Add unit tests for any new features or bug fixes.
- Ensure all tests pass (`pytest tests/`).
- Do not introduce heavy dependencies (no GUI toolkits, heavyweight web frameworks, or remote cloud SDKs).
