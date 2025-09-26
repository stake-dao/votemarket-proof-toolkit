# Publishing Guide for votemarket-toolkit

This guide covers how to build and publish the `votemarket-toolkit` package.

## Prerequisites

- Python >=3.10
- uv installed (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- PyPI account (for publishing)
- Configured PyPI credentials (see below)

## Package Structure

The package publishes only what's in `src/votemarket_toolkit/`:
- ✅ `votemarket_toolkit/` module
- ❌ `docs/` (not included in package)
- ❌ `examples/` (not included in package)
- ❌ `tests/` (not included in package)

## Building the Package

### Using uv (Recommended)

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build wheel and source distribution
uv build

# This creates:
# - dist/votemarket_toolkit-0.1.0-py3-none-any.whl (wheel)
# - dist/votemarket_toolkit-0.1.0.tar.gz (source)
```

### Alternative: Using build module

```bash
# Install build tools
uv pip install build

# Build
uv run python -m build
```

## Testing the Build Locally

Before publishing, test your package locally:

```bash
# Create a test virtual environment
uv venv test-env
source test-env/bin/activate  # On Windows: test-env\Scripts\activate

# Install the built package
uv pip install dist/votemarket_toolkit-0.1.0-py3-none-any.whl

# Test imports
python -c "from votemarket_toolkit.shared import registry; print('✅ Import successful')"

# Deactivate and clean up
deactivate
rm -rf test-env
```

## Configuring PyPI Credentials

### Option 1: Using .pypirc file

Create `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-xxx...  # Your PyPI API token

[testpypi]
username = __token__
password = pypi-xxx...  # Your TestPyPI API token
```

### Option 2: Using Environment Variables

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-xxx...  # Your PyPI API token
```

## Publishing to PyPI

### 1. Test with TestPyPI First (Recommended)

```bash
# Install twine
uv pip install twine

# Upload to TestPyPI
uv run twine upload --repository testpypi dist/*

# Test installation from TestPyPI
uv pip install --index-url https://test.pypi.org/simple/ votemarket-toolkit
```

### 2. Publish to Production PyPI

```bash
# Upload to PyPI
uv run twine upload dist/*

# Verify installation
uv pip install votemarket-toolkit
```

## Version Management

### Semantic Versioning

Follow semantic versioning (MAJOR.MINOR.PATCH):
- **MAJOR**: Breaking API changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Updating Version

1. Edit `pyproject.toml`:
   ```toml
   [project]
   version = "0.2.0"  # Update version here
   ```

2. Commit the change:
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.2.0"
   ```

3. Tag the release:
   ```bash
   git tag v0.2.0
   git push origin main
   git push origin v0.2.0
   ```

## GitHub Release Automation (Optional)

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.cargo/bin" >> $GITHUB_PATH
      
      - name: Build package
        run: uv build
      
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: |
          uv pip install twine
          uv run twine upload dist/*
```

Then add your PyPI token to GitHub Secrets as `PYPI_API_TOKEN`.

## Complete Publishing Checklist

- [ ] Run tests: `make test` (if available)
- [ ] Update version in `pyproject.toml`
- [ ] Update CHANGELOG.md (if maintaining one)
- [ ] Clean build artifacts: `rm -rf dist/ build/`
- [ ] Build package: `uv build`
- [ ] Test locally: `uv pip install dist/*.whl`
- [ ] Upload to TestPyPI: `uv run twine upload --repository testpypi dist/*`
- [ ] Test from TestPyPI: `uv pip install --index-url https://test.pypi.org/simple/ votemarket-toolkit`
- [ ] Upload to PyPI: `uv run twine upload dist/*`
- [ ] Git commit and push
- [ ] Create git tag: `git tag v0.1.0 && git push origin v0.1.0`
- [ ] Create GitHub release (optional)

## Troubleshooting

### Build Issues

```bash
# Ensure you have latest uv
uv self update

# Clear all caches
rm -rf dist/ build/ *.egg-info
uv cache clean
```

### Import Issues After Publishing

Check the package structure:
```bash
# Download and inspect the published package
pip download votemarket-toolkit --no-deps
tar -tzf votemarket-toolkit-*.tar.gz | head -20
```

### Version Conflicts

Always increment the version number. PyPI doesn't allow overwriting existing versions.

## Users Installing the Package

Once published, users can install with:

```bash
# From PyPI (once published)
pip install votemarket-toolkit
# or
uv pip install votemarket-toolkit

# From GitHub (current)
pip install git+https://github.com/stake-dao/votemarket-proof-toolkit.git
# or
uv pip install git+https://github.com/stake-dao/votemarket-proof-toolkit.git
```