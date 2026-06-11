# Contributing to I.R.I.S.
**Intelligent Rendering & Image Synthesis**

Thank you for your interest in contributing to I.R.I.S.!  
This project aims to be an open, flexible and hardware-friendly platform for AI image generation.

---

## Table of Contents
1. Code of Conduct  
2. Ways to Contribute  
3. Development Setup  
4. Pull Request Workflow  
5. Coding Standards  
6. Testing Guidelines  
7. Discord & Configuration  
8. Getting Help  

---

## Code of Conduct

This project follows a simple principle:

> **Be respectful, inclusive, and constructive.**

Harassment, hate speech, discrimination, or intentionally harmful contributions are not tolerated.

By contributing, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Ways to Contribute

### 🐛 Bug Reports
Before opening a new issue:
- Check existing issues
- Test with the latest version
- Provide clear reproduction steps

**Bug Report Template**
\`\`\`markdown
**Description**
Clear and concise description of the issue.

**Steps to Reproduce**
1. Go to ...
2. Click ...
3. Error appears

**Expected Behavior**
What should happen instead?

**Environment**
- OS:
- GPU:
- VRAM:
- Python:
- CUDA / ROCm:
\`\`\``

---

### ✨ Feature Requests

\`\`\`markdown
**Problem**
What limitation does this solve?

**Proposed Solution**
Describe your idea.

**Alternatives**
Any other approaches considered?

**Why for I.R.I.S.?**
How does this fit the project's philosophy?
\`\`\`

---

### 🧠 Code Contributions

We welcome:

* Performance optimizations
* New AI models
* Scheduler & sampler improvements
* UI/UX enhancements
* Memory management improvements
* AMD / Intel / Apple compatibility
* Documentation improvements

Large features should be discussed via Issues first.

---

## Development Setup

### 1. Fork & Clone

\`\`\`bash
git clone https://github.com/YOUR_USERNAME/IRIS.git
cd IRIS
git remote add upstream https://github.com/ORIGINAL_OWNER/IRIS.git
\`\`\`

---

### 2. Create a Branch

\`\`\`bash
git checkout -b feature/my-feature
# or
git checkout -b fix/my-bug
\`\`\`

**Branch naming**

* `feature/` – New features
* `fix/` – Bug fixes
* `docs/` – Documentation
* `refactor/` – Refactoring
* `test/` – Tests

---

### 3. Python Environment

\`\`\`bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
\`\`\`

---

### 4. Environment Configuration

Create a `.env` file:

\`\`\`env
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

DISCORD_BOT_TOKEN=your_token
DISCORD_BOT_OWNER_ID=your_id
DISCORD_BOT_ID=bot_id

DISCORD_CHANNEL_NEW_IMAGES=channel_id
DISCORD_CHANNEL_VARIATIONS=channel_id
DISCORD_CHANNEL_UPSCALED=channel_id
\`\`\`

---

### 5. Running the Project

\`\`\`bash
# Auto-start based on settings.json
python src/start.py

# Force start without Discord bot
python src/start.py --no-bot
\`\`\`

The startup behavior is controlled by `settings.json`:
- `discordEnabled: true` → Web UI + Discord Bot
- `discordEnabled: false` → Web UI only

---

## Pull Request Workflow

### Commit Style

\`\`\`text
type: short description

Optional longer explanation
Fixes #issue_number
\`\`\`

**Types**

* `feat` – New feature
* `fix` – Bug fix
* `docs` – Documentation
* `refactor` – Code cleanup
* `test` – Tests
* `chore` – Maintenance

---

### Pull Request Checklist

* [ ] Code follows style guidelines
* [ ] Tested locally
* [ ] No breaking changes (or documented)
* [ ] Documentation updated if needed

---

## Coding Standards

### Python Guidelines

* Follow **PEP 8**
* Use type hints
* Use docstrings
* Max line length: **100**
* Prefer clarity over cleverness

**Good Example**

\`\`\`python
def generate_image(prompt: str, steps: int) -> bool:
    """Generate an image from a text prompt."""
    return True
\`\`\`

---

## Project Structure

\`\`\`text
src/
├── api/            # FastAPI backend
├── core/           # Generation logic
├── services/       # Discord & integrations
├── utils/          # Helpers & logging
├── start.py        # Entry point

static/
├── assets/
├── config/
├── data/

outputs/
logs/
tests/
\`\`\`

---

## Testing Guidelines

\`\`\`bash
pytest
pytest -v
pytest --cov=src
\`\`\`

Tests are encouraged but not mandatory for small fixes.

---

## Discord & Community

* Use GitHub Issues for bugs & features
* Use Discussions for ideas & questions
* Be respectful and constructive

---

## License

By contributing, you agree that your work will be released under the **MIT License**.

---

Thank you for contributing to **I.R.I.S.**
Together we build an open, flexible and future-proof AI image generation platform.
