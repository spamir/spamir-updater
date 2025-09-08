# Publishing Spamir Updater to PyPI

## Prerequisites

1. **PyPI Account**: Create an account at [pypi.org](https://pypi.org)
2. **Test PyPI Account** (optional): Create an account at [test.pypi.org](https://test.pypi.org) for testing
3. **Install Build Tools**:
```bash
pip install --upgrade pip setuptools wheel twine
```

## Pre-Publishing Checklist

- [ ] Update version number in `setup.py`
- [ ] Update `README.md` with latest documentation
- [ ] Test the module locally
- [ ] Commit all changes to git
- [ ] Create a git tag for the version

## Build the Package

1. **Clean previous builds**:
```bash
rm -rf dist/ build/ *.egg-info/
```

2. **Build the distribution packages**:
```bash
python setup.py sdist bdist_wheel
```

This creates:
- `dist/spamir-updater-1.0.0.tar.gz` (source distribution)
- `dist/spamir_updater-1.0.0-py3-none-any.whl` (wheel distribution)

## Test on TestPyPI (Recommended)

1. **Upload to TestPyPI**:
```bash
twine upload --repository testpypi dist/*
```

2. **Test installation from TestPyPI**:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ spamir-updater
```

3. **Verify it works**:
```python
from lib.updater_client import UpdaterClient
print("Import successful!")
```

## Publish to PyPI

1. **Upload to PyPI**:
```bash
twine upload dist/*
```

You'll be prompted for your PyPI username and password.

2. **Using API Token (Recommended)**:
   - Generate an API token at https://pypi.org/manage/account/token/
   - Use `__token__` as username
   - Use the token as password

3. **Configure `.pypirc` for automation** (optional):
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-<your-token-here>

[testpypi]
username = __token__
password = pypi-<your-test-token-here>
```

## Post-Publishing

1. **Install from PyPI**:
```bash
pip install spamir-updater
```

2. **Verify installation**:
```bash
python -c "from lib.updater_client import UpdaterClient; print('Success!')"
```

3. **Create GitHub Release**:
   - Tag the version: `git tag v1.0.0`
   - Push tags: `git push --tags`
   - Create release on GitHub with changelog

## Version Management

When releasing updates:

1. **Semantic Versioning**: Follow MAJOR.MINOR.PATCH
   - MAJOR: Breaking API changes
   - MINOR: New features, backwards compatible
   - PATCH: Bug fixes

2. **Update version in**:
   - `setup.py` (version field)
   - `lib/__init__.py` (if you have __version__)
   - Git tag

## Troubleshooting

### Common Issues:

1. **Name already taken**: Change package name in `setup.py`
2. **Invalid classifier**: Check valid classifiers at https://pypi.org/classifiers/
3. **Missing long_description**: Ensure README.md exists
4. **Authentication failed**: Check token or credentials

### Useful Commands:

```bash
# Check package before upload
twine check dist/*

# Upload only specific files
twine upload dist/spamir-updater-1.0.0.tar.gz

# Verbose upload for debugging
twine upload --verbose dist/*
```

## Alternative: Using GitHub Actions

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: actions/setup-python@v2
      with:
        python-version: '3.x'
    - name: Install dependencies
      run: |
        pip install setuptools wheel twine
    - name: Build and publish
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: |
        python setup.py sdist bdist_wheel
        twine upload dist/*
```

Add your PyPI token as a GitHub secret named `PYPI_API_TOKEN`.