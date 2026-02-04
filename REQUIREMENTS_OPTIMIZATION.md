# Requirements Optimization Summary

## Overview
Optimized dependency management across the Empirico AI CDSS project to reduce bloat, improve security, and simplify maintenance.

## Changes Made

### Backend (`backend/requirements.txt`)

**Before:** 172 dependencies (many transitive/unused)  
**After:** ~25 direct production dependencies

#### Removed Unused Dependencies
- `langchain`, `langchain-community`, `langchain-core` - Not used in codebase
- `pandas`, `numpy` - Only used in scripts (moved to optional dependencies)
- `torch`, `openai-whisper` - Large dependencies, made optional (commented out)
- Many transitive dependencies that are automatically installed

#### Optimized Structure
- **Core Framework**: FastAPI, Uvicorn, Starlette, Pydantic
- **Database**: SQLAlchemy, Alembic, psycopg2-binary
- **Security**: python-jose, PyJWT, passlib, bcrypt, cryptography
- **Google Cloud**: vertexai, google-genai, google-auth
- **Vector DB**: pymilvus
- **OpenAI**: openai (for Azure OpenAI embeddings)
- **Utilities**: python-dotenv, tenacity, httpx, python-dateutil

#### Version Pinning
- Added upper bounds to prevent breaking changes
- Used compatible version ranges (e.g., `>=0.115.0,<0.116.0`)

### Development Dependencies (`backend/requirements-dev.txt`)

Separated development dependencies into a separate file:
- Testing: pytest, pytest-asyncio, pytest-cov, pytest-mock, coverage
- Code Quality: black, isort, flake8, mypy
- Security: bandit, safety
- Dev Tools: watchfiles (for auto-reload)

### Script Dependencies (`backend/pyproject.toml`)

Moved pandas and numpy to optional dependencies under `[project.optional-dependencies.scripts]` since they're only used in data ingestion scripts.

### Frontend (`frontend/package.json`)

**Status:** Already optimized - minimal dependencies

Added:
- `engines` field to specify Node.js and npm version requirements

## Benefits

1. **Reduced Installation Time**: Fewer packages to download and install
2. **Smaller Docker Images**: Less dependencies = smaller container size
3. **Improved Security**: Fewer dependencies = smaller attack surface
4. **Easier Maintenance**: Clear separation of production vs. dev dependencies
5. **Version Control**: Upper bounds prevent unexpected breaking changes
6. **Clear Dependencies**: Only direct dependencies listed, transitive ones auto-installed

## Installation

### Production
```bash
pip install -r backend/requirements.txt
```

### Development
```bash
pip install -r backend/requirements-dev.txt
```

### With Scripts Support
```bash
pip install -e ".[scripts]"
```

## Migration Notes

1. **Transcription Service**: 
   - The app now starts successfully without Whisper dependencies
   - If you need audio transcription, uncomment `openai-whisper` and `torch` in `requirements.txt`
   - The transcription endpoints will return 503 if dependencies are not installed
   - Install with: `pip install openai-whisper torch` (or uncomment in requirements.txt)
2. **Data Scripts**: If running data ingestion scripts, install with: `pip install -e ".[scripts]"`
3. **Existing Environments**: Consider recreating your virtual environment for a clean install:
   ```bash
   rm -rf venv
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -r backend/requirements-dev.txt
   ```

## Verification

To verify all dependencies are correctly installed:
```bash
# Check for missing imports
python -c "import fastapi, sqlalchemy, pydantic, vertexai, pymilvus, openai; print('✅ Core dependencies OK')"

# Run security scan
bandit -r backend/src

# Run type checking
mypy backend/src
```

## Estimated Size Reduction

- **Before**: ~500MB+ (with all transitive dependencies)
- **After**: ~200-300MB (production dependencies only)
- **Savings**: ~40-60% reduction in dependency footprint

