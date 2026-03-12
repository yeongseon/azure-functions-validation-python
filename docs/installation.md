# Installation

`azure-functions-validation` targets the **Azure Functions Python v2 programming model**.

## Requirements

- Python 3.10+
- `azure-functions`
- Azure Functions Python **v2** (`func.FunctionApp` with decorators)

> This package does not support the legacy `function.json`-based v1 programming model.

## Version Compatibility

| Component | Supported Range | Notes |
| --- | --- | --- |
| Python | 3.10+ | Project metadata currently declares `>=3.10,<3.15`. |
| Pydantic | v2 (`>=2.0,<3.0`) | Validation models should inherit from `pydantic.BaseModel`. |
| `azure-functions` | Required | Use with Python v2 decorator-based `FunctionApp`. |

Compatibility expectations:

- Request and response models are based on Pydantic v2 behavior.
- Function definitions should follow the Python v2 decorator style.
- Validation errors are returned as HTTP `422` with a JSON `detail` list.

## From PyPI

```bash
pip install azure-functions-validation
```

Ensure your Function App dependencies include:

```text
azure-functions
azure-functions-validation
```

If you pin dependencies, keep `pydantic` in the v2 major version.

## Verify Installation

Run the following command after installation:

```bash
python -c "import azure_functions_validation; print(azure_functions_validation.__version__)"
```

Expected outcome:

- the command prints a version string such as `0.5.0`
- no import errors are raised

You can also verify package metadata from your environment:

```bash
pip show azure-functions-validation
```

Check that your active environment is the same one used by your Function App.

## Local Development

```bash
git clone https://github.com/yeongseon/azure-functions-validation.git
cd azure-functions-validation
make install
```

All project maintenance commands should go through the Makefile.

## Upgrading

Upgrade to the latest published version:

```bash
pip install --upgrade azure-functions-validation
```

Recommended upgrade workflow:

1. Upgrade in a dedicated virtual environment.
2. Reinstall or confirm compatible `azure-functions` and Pydantic v2 versions.
3. Run your local Azure Functions smoke tests.
4. Confirm validation and response contracts still match your API expectations.

For deterministic deployments, pin an explicit version in your dependency file.

## Troubleshooting

### ImportError: No module named `azure_functions_validation`

- Confirm installation ran in the correct environment.
- Run `python -m pip install azure-functions-validation`.
- Verify with `python -c "import azure_functions_validation"`.

### Pydantic version mismatch

- Ensure Pydantic is v2 (`pip show pydantic`).
- If v1 is installed transitively, pin `pydantic>=2,<3` and reinstall.

### Function app starts but validation decorator behavior is missing

- Confirm you are using the Python v2 programming model (`func.FunctionApp()`).
- Confirm your handler uses decorator registration (`@app.route`, `@validate_http`).

### Runtime dependency drift in Azure

- Rebuild deployment artifacts from a clean environment.
- Confirm `requirements.txt` includes both `azure-functions` and
  `azure-functions-validation`.
- Verify the deployed Python runtime version is compatible with your lockfile.
