# Environment Setup

Follow these steps to create an isolated Python environment for working with the NANDA Registry Service.

## 1. Prerequisites
- macOS or Linux shell (bash/zsh)
- Python 3.10+ recommended
- (Optional) Docker if you want a local MongoDB instance

Check Python:
```bash
python3 --version
```

## 2. Create and Activate Virtual Environment

Manual steps:
```bash
cd nanda-index
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
```

Helper script (recommended):
```bash
cd nanda-index
source scripts/create_venv.sh
```

This will:
- Create `.venv` if missing
- Activate it
- Install dependencies from `requirements.txt`

## 3. Install Dependencies (If Not Using Script)
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. (Optional) Start MongoDB Locally
```bash
docker run -d --name mongo -p 27017:27017 mongo:6
export MONGODB_URI="mongodb://localhost:27017"
```

## 5. Run the Service
```bash
export PORT=6900
python registry.py
```

## 6. Run Tests
```bash
pip install pytest
pytest -q
```

## 7. Deactivate Environment
```bash
deactivate
```

## 8. Updating Dependencies
When adding a new dependency:
```bash
pip install <package>
pip freeze | grep <package>
# (Optionally) append version pin to requirements.txt
```

## 9. Troubleshooting
- If `pip` installs globally, ensure you activated the venv (`which python` should point inside `.venv`).
- If Mongo connection fails, confirm container is running: `docker ps`.
- To recreate environment: `rm -rf .venv && source scripts/create_venv.sh`.

## 10. Next Improvements
- Add a `Makefile` with targets (`make venv`, `make test`, `make run`).
- Add `.env` file support via `python-dotenv`.
- Provide Docker Compose for Mongo + registry.
