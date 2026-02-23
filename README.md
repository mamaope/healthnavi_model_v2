# Empirico - AI-Powered Medical Knowledge Base

<div align="center">

![Empirico Logo](https://via.placeholder.com/200x60?text=Empirico)

**Empirico** is a secure, HIPAA/GDPR/ISO 13485 compliant AI-powered medical knowledge base that uses Retrieval-Augmented Generation (RAG) to provide healthcare professionals with evidence-based medical information and guidance.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Platforms](#platforms)
- [Security & Compliance](#security--compliance)
- [Development](#development)
- [Testing](#testing)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

---

## 🎯 Overview

**Empirico** is a comprehensive medical knowledge base platform designed to help healthcare professionals access evidence-based medical information through AI-powered assistance. The system combines advanced language models with a curated medical knowledge base to provide evidence-based guidance, drug information, clinical guidelines, and treatment recommendations.

### What Empirico Does

- **Medical Information Access**: Provides AI-powered access to evidence-based medical information, treatment planning, and clinical queries
- **Drug Information**: Access comprehensive drug dosing, interactions, and prescribing information
- **Clinical Guidelines**: References to WHO, ADA, and other authoritative medical guidelines
- **Evidence-Based Answers**: Uses RAG (Retrieval-Augmented Generation) to ground responses in medical literature
- **Multi-Platform Access**: Available on web and mobile (Android) platforms

---

## ✨ Key Features

### 🔐 Authentication & User Management
- **Multiple Authentication Methods**
  - Email/password registration and login
  - Google Sign-In (OAuth 2.0) for web and mobile
  - Secure JWT-based session management
  - Password reset functionality
  - Email verification
- **User Roles**: Support for healthcare professionals, administrators, and super admins
- **Account Management**: Profile management, account closure, and data deletion requests

### 💬 AI-Powered Medical Information Chat
- **Interactive Chat Interface**: Real-time conversation with AI medical information assistant
- **Deep Search Mode**: Enhanced search capabilities for comprehensive responses
- **Session Management**: Create and manage multiple conversation sessions
- **Message History**: Complete conversation history with search capabilities
- **Rich Formatting**: Markdown support with proper medical formatting, aligned between web and Android (headings, spacing, lists, blockquotes)
- **Feedback System**: Rate responses as helpful/not helpful to improve the system

### 📊 Survey & Research
- **Pilot Program Surveys**: Baseline, mid-pilot, and final surveys
- **PMF (Product-Market Fit) Analysis**: Integrated survey system for product validation
- **Survey Management**: Admin dashboard for survey configuration and visibility

### 📱 Multi-Platform Support
- **Web Application**: React-based responsive web interface
- **Android Mobile App**: Native Android app with offline capabilities
- **Cross-Platform Sync**: Seamless synchronization across devices

### 🔒 Security & Compliance
- **HIPAA Compliance**: Protected Health Information (PHI) encryption and audit logging
- **GDPR Compliance**: Data protection and privacy controls
- **ISO 13485**: Medical device software quality management
- **SOC 2 Type II**: Security, availability, and confidentiality controls
- **Data Encryption**: AES-256 encryption for sensitive medical data
- **Audit Trails**: Complete audit logging for compliance

### 📈 Admin Dashboard
- **User Management**: User administration and role management
- **Device Statistics**: Track device types (phone, tablet, laptop) for analytics
- **Session Analytics**: Monitor usage patterns and system health
- **Survey Management**: Configure and manage survey programs

---

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │   FastAPI       │    │   PostgreSQL    │
│   (React/Vite)  │◄──►│   Backend       │◄──►│   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                      │                        │
         │                      ▼                        │
         │              ┌─────────────────┐             │
         │              │   Vector Store  │             │
         │              │   (Zilliz)      │             │
         │              └─────────────────┘             │
         │                      │                        │
         │                      ▼                        │
         │              ┌─────────────────┐             │
         │              │   AI Models     │             │
         │              │   (Vertex AI)   │             │
         │              └─────────────────┘             │
         │                                              │
         └──────────────────────────────────────────────┘
                    ┌─────────────────┐
                    │  Android App    │
                    │  (Kotlin)       │
                    └─────────────────┘
```

### Technology Stack

**Backend**
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15+
- **Vector Database**: Zilliz Cloud (Milvus)
- **AI/ML**: Google Vertex AI (Gemini models)
- **Authentication**: JWT, OAuth 2.0
- **ORM**: SQLAlchemy
- **Migrations**: Alembic

**Frontend (Web)**
- **Framework**: React with TypeScript
- **Build Tool**: Vite
- **UI Library**: Material UI components
- **State Management**: React hooks and context
- **HTTP Client**: Axios

**Mobile (Android)**
- **Language**: Kotlin
- **UI Framework**: Jetpack Compose
- **Architecture**: MVVM (Model-View-ViewModel)
- **Networking**: Retrofit + OkHttp
- **Navigation**: Jetpack Navigation Compose

**Infrastructure**
- **Containerization**: Docker & Docker Compose
- **Cloud Services**: Google Cloud Platform (Vertex AI)
- **Vector Database**: Zilliz Cloud

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **PostgreSQL 15+**
- **Docker & Docker Compose** (recommended)
- **Google Cloud Platform** account with Vertex AI enabled
- **Node.js 18+** (for frontend development)
- **Android Studio** (for mobile development)

### Docker Deployment (Recommended)

The fastest way to get started:

```bash
# Clone the repository
git clone https://github.com/your-org/empirico.git
cd empirico

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f api

# Access the application
# Web: http://localhost:3000
# API: http://localhost:8050/api/v2
# API Docs: http://localhost:8050/api/v2/docs
```

On first run, the API container runs database migrations and seeds an admin user if none exists (override with `ADMIN_EMAIL`, `ADMIN_PASSWORD`, etc. in `.env`). To seed an admin manually: `cd backend && python scripts/seed_admin_user.py`.

---

## 📦 Installation

### Backend Setup

1. **Create virtual environment**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Run database migrations**
```bash
alembic upgrade head
```

5. **Seed admin user** (optional, if not using Docker)
```bash
python scripts/seed_admin_user.py
```

6. **Start the backend**
```bash
uvicorn healthnavi.main:app --reload --host 0.0.0.0 --port 8050
```

### Frontend Setup

1. **Install dependencies**
```bash
cd frontend
npm install
```

2. **Start development server**
```bash
npm run dev
```

3. **Access the application**
```
http://localhost:5173
```

### Mobile App Setup

1. **Open in Android Studio**
```bash
cd mobile
# Open the project in Android Studio
```

2. **Configure API URL** (if using local backend)
   - Edit `local.properties` or `gradle.properties`
   - Set `API_BASE_URL=http://10.0.2.2:8050/api/v2/` (emulator)
   - Or use your machine's IP for physical devices

3. **Build and run**
```bash
./gradlew assembleDebug
./gradlew installDebug
```

---

## ⚙️ Configuration

### Required Environment Variables

```bash
# Security
SECRET_KEY=your-super-secure-secret-key-min-32-chars
ENCRYPTION_KEY=your-encryption-key-min-32-chars

# Database
DB_USER=empirico_user
DB_PASSWORD=your-secure-db-password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=empirico_cdss

# Google Cloud / Vertex AI
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Google OAuth (for authentication)
GOOGLE_CLIENT_ID=your-web-oauth-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://your-domain.com/api/v2/auth/google/callback

# Vector Database (Zilliz)
MILVUS_URI=https://your-cluster.zillizcloud.com
MILVUS_TOKEN=your-milvus-token
MILVUS_COLLECTION_NAME=medical_knowledge

# Application
ENV=production
DEBUG=false
LOG_LEVEL=INFO
CORS_ORIGINS=["https://your-frontend-domain.com"]
```

### Google Cloud Setup

1. **Create a Google Cloud Project**
   - Enable Vertex AI API
   - Enable OAuth consent screen

2. **Create Service Account**
   - Go to IAM & Admin > Service Accounts
   - Create service account with Vertex AI User role
   - Download JSON key file

3. **Configure OAuth**
   - Create OAuth 2.0 Client IDs (Web and Android)
   - Add authorized redirect URIs
   - Configure Android OAuth client with package name and SHA-1

---

## 📚 API Documentation

### Base URL
```
Production: https://empirico.ai/api/v2/
Development: http://localhost:8050/api/v2/
```

### Interactive API Documentation
- **Swagger UI**: `/api/v2/docs`
- **ReDoc**: `/api/v2/redoc`

### Key Endpoints

#### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `POST /auth/google-sign-in-mobile` - Google Sign-In (mobile)
- `GET /auth/me` - Get current user profile
- `POST /auth/refresh` - Refresh access token

#### Clinical Chat
- `POST /diagnosis/diagnose` - Generate AI medical information response
- `POST /diagnosis/diagnose/stream` - Streamed AI responses
- `POST /diagnosis/feedback` - Submit message feedback
- `GET /chat/sessions` - List chat sessions
- `POST /chat/sessions` - Create new session
- `GET /chat/sessions/{id}/messages` - Get session messages

#### Admin
- `GET /admin/metrics` - Get system metrics
- `GET /admin/metrics/devices` - Get device statistics
- `GET /admin/users` - List users

#### Health
- `GET /health` - Health check endpoint

---

## 📱 Platforms

### Web Application
- **URL**: https://empirico.ai
- **Features**: Full-featured web interface with all capabilities
- **Browser Support**: Modern browsers (Chrome, Firefox, Safari, Edge)

### Android Mobile App
- **Package**: `ai.empirico.app`
- **Minimum SDK**: Android 8.0 (API 26)
- **Target SDK**: Android 14+ (API 36)
- **Download**: Available on Google Play Store
- **Features**: 
  - Offline-capable chat interface
  - Session management
  - Google Sign-In integration
  - AI response formatting consistent with web app (headings, spacing, lists, blockquotes)
  - Push notifications (coming soon)
- **Release builds**: For Google Sign-In to work in release APKs, add your **release keystore SHA-1** to the Android OAuth client in Google Cloud Console (APIs & Services → Credentials → your Android OAuth 2.0 client).

---

## 🔒 Security & Compliance

### Security Features

- **Authentication**: JWT tokens with secure refresh mechanism
- **Authorization**: Role-based access control (RBAC)
- **Data Encryption**: AES-256 encryption for sensitive data
- **Input Validation**: Comprehensive input sanitization
- **Rate Limiting**: Protection against abuse
- **Audit Logging**: Complete audit trail for compliance
- **PHI Protection**: Automatic PHI detection and sanitization in logs

### Compliance Standards

- **HIPAA**: Healthcare data protection and privacy
- **GDPR**: European data protection regulation compliance
- **ISO 13485**: Medical device software quality management
- **SOC 2 Type II**: Security and availability controls

### Security Best Practices

1. **Always use HTTPS** in production
2. **Store secrets securely** using environment variables or secrets management
3. **Regular security updates** for dependencies
4. **Monitor audit logs** for suspicious activity
5. **Implement network security** (firewalls, VPCs)

---

## 💻 Development

### Repository Structure

```
empirico/
├── backend/                 # FastAPI backend
│   ├── src/healthnavi/     # Main application code
│   │   ├── api/v1/         # API endpoints
│   │   ├── core/           # Core utilities
│   │   ├── models/         # Database models
│   │   ├── services/       # Business logic
│   │   └── schemas/        # Pydantic schemas
│   ├── alembic/            # Database migrations
│   ├── scripts/            # Utility scripts
│   └── tests/              # Test suite
├── frontend/                # React web application
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API clients
│   │   └── styles/         # CSS/styles
│   └── public/             # Static assets
├── mobile/                  # Android mobile app
│   └── app/
│       └── src/main/java/ai/empirico/app/
│           ├── data/       # Data layer
│           ├── ui/         # UI layer
│           └── navigation/ # Navigation
├── docker-compose.yml       # Docker orchestration
└── README.md               # This file
```

### Code Quality

```bash
# Format code
black backend/src/healthnavi
isort backend/src/healthnavi

# Lint code
flake8 backend/src/healthnavi
mypy backend/src/healthnavi

# Security scan
bandit -r backend/src/healthnavi
safety check
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## 🧪 Testing

### Backend Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=healthnavi --cov-report=html

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m security
```

### Frontend Tests

```bash
cd frontend
npm test
npm run test:coverage
```

### Mobile Tests

```bash
cd mobile
./gradlew test
./gradlew connectedAndroidTest
```

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes** following our coding standards
4. **Write tests** for new functionality
5. **Update documentation** as needed
6. **Commit your changes** (`git commit -m 'Add amazing feature'`)
7. **Push to the branch** (`git push origin feature/amazing-feature`)
8. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 for Python code
- Use TypeScript for frontend code
- Follow Kotlin coding conventions for mobile
- Write comprehensive tests
- Update documentation
- Ensure security best practices

---

## 📊 Monitoring & Logging

### Logging

- **Structured Logging**: JSON-formatted logs for easy parsing
- **PHI Sanitization**: Automatic removal of PHI from logs
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Audit Logging**: Complete audit trail for compliance

### Monitoring

- **Health Checks**: `/api/v2/health` endpoint
- **Performance Metrics**: Response times, throughput
- **Error Tracking**: Error rates and patterns
- **Security Metrics**: Failed logins, suspicious activity

---

## 🆘 Support

### Documentation

- **API Documentation**: Interactive docs at `/api/v2/docs` (Swagger) and `/api/v2/redoc` (ReDoc). Architecture and security overview are in the [Architecture](#-architecture) and [Security & Compliance](#-security--compliance) sections above.

### Getting Help

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/your-org/empirico/issues)
- **Discussions**: Join discussions in [GitHub Discussions](https://github.com/your-org/empirico/discussions)
- **Email**: support@empirico.ai

### Security Issues

For security vulnerabilities, please email **security@empirico.ai** instead of using the public issue tracker.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Important Disclaimers

**Medical Information Base Disclaimer**: Empirico is a medical information base designed to provide healthcare professionals with evidence-based medical information. It is not intended to replace clinical judgment or serve as a substitute for professional medical advice, diagnosis, or treatment. Always verify information and consult with qualified healthcare professionals for medical decisions.

**Regulatory Compliance**: Users are responsible for ensuring compliance with all applicable healthcare regulations, including HIPAA, GDPR, and local medical device regulations in their jurisdiction.

**Data Privacy**: Empirico handles sensitive medical information. Users must ensure proper data protection measures are in place and comply with all applicable privacy laws.

---

## 🙏 Acknowledgments

- **Google Vertex AI** for AI/ML capabilities
- **Zilliz** for vector database infrastructure
- **FastAPI** for the excellent web framework
- **React** and **Jetpack Compose** communities

---

<div align="center">

**Built with ❤️ for healthcare professionals**

[Website](https://empirico.ai) • [Documentation](https://docs.empirico.ai) • [Support](mailto:support@empirico.ai)

</div>
