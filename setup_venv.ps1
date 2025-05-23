python -m venv .\venv
.\venv\Scripts\Activate.ps1
pip install -r .\requirements-develop.txt
pip install -e .
pre-commit install