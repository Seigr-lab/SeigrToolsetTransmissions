# Environment Setup

## Conda Environment for SeigrToolsetTransmissions

This project uses a dedicated conda environment to ensure clean dependency isolation and reproducibility.

### Prerequisites

- Anaconda or Miniconda installed
- Python 3.9+

### Creating the Environment

```bash
# From project root
conda env create -f environment.yml
```

This creates an environment named `seigr-stt` with:

- Python 3.9
- pytest and pytest-asyncio for testing
- pytest-cov for coverage reporting
- seigr-toolset-crypto (STC >=0.4.0) - the ONLY external cryptographic dependency

### Activating the Environment

```bash
conda activate seigr-stt
```

### Installing the Package in Development Mode

```bash
# After activating the environment
pip install -e .
```

This installs the package in editable mode, allowing you to make changes without reinstalling.

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=seigr_toolset_transmissions --cov-report=html

# Run specific test file
pytest tests/test_frame.py -v

# Run specific test
pytest tests/test_frame.py::TestSTTFrame::test_create_frame -v
```

### Updating Dependencies

If you need to update dependencies:

```bash
# Update environment.yml, then:
conda env update -f environment.yml --prune
```

### Deactivating the Environment

```bash
conda deactivate
```

### Removing the Environment

```bash
conda env remove -n seigr-stt
```

### Environment Verification

Verify the environment is correctly set up:

```bash
conda activate seigr-stt
python -c "import seigrtc; print('STC imported successfully')"
python -c "from seigr_toolset_transmissions import STTNode; print('STT imports successful')"
pytest tests/test_varint.py -v
```

All commands should succeed without errors.

### IDE Configuration

**VS Code:**
1. Open Command Palette (Ctrl+Shift+P)
2. Select "Python: Select Interpreter"
3. Choose the `seigr-stt` conda environment

**PyCharm:**
1. File → Settings → Project → Python Interpreter
2. Add Interpreter → Conda Environment → Existing
3. Select the `seigr-stt` environment

### Environment Export

To share the exact environment:

```bash
# Export with exact versions
conda env export > environment-lock.yml

# Or just the manually specified packages
conda env export --from-history > environment.yml
```

### Troubleshooting

**Issue: seigr-toolset-crypto not found**

```bash
pip install seigr-toolset-crypto>=0.3.1
```

**Issue: pytest not found**
```bash
conda install pytest pytest-asyncio pytest-cov
```

**Issue: Import errors**
```bash
# Reinstall in development mode
pip install -e .
```

**Issue: Old environment cached**
```bash
conda env remove -n seigr-stt
conda env create -f environment.yml
```
