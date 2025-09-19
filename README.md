# HealthNavi AI CDSS - Enhanced Security Edition

## 🏥 Medical AI Clinical Decision Support System

**HealthNavi AI CDSS** is a secure, HIPAA/GDPR/ISO 13485 compliant AI-powered Clinical Decision Support System that uses Retrieval-Augmented Generation (RAG) to assist healthcare professionals with medical decision-making.

## 🔒 Security Features

### **Medical Software Security Standards**
- **HIPAA Compliance**: Protected Health Information (PHI) encryption and audit logging
- **GDPR Compliance**: Data protection and privacy controls
- **ISO 13485**: Medical device software quality management
- **SOC 2 Type II**: Security, availability, and confidentiality controls

### **Authentication & Authorization**
- **JWT-based Authentication**: Secure token-based authentication
- **Password Security**: Bcrypt hashing with salt, strong password requirements
- **Rate Limiting**: Protection against brute force attacks
- **Session Management**: Secure session handling with refresh tokens
- **Account Lockout**: Automatic account locking after failed attempts

### **Data Protection**
- **PHI Encryption**: AES-256 encryption for sensitive medical data
- **Secure Logging**: PHI sanitization in logs
- **Input Validation**: Comprehensive input sanitization and validation
- **Audit Trails**: Complete audit logging for compliance
- **Data Retention**: Configurable data retention policies

### **API Security**
- **CORS Protection**: Configurable Cross-Origin Resource Sharing
- **Request Validation**: Pydantic-based input validation
- **Error Handling**: Secure error messages without information leakage
- **Rate Limiting**: API endpoint rate limiting
- **Security Headers**: Comprehensive security headers

## 🚀 Quick Start

### **Prerequisites**
- Python 3.11+
- PostgreSQL 15+
- Docker & Docker Compose
- Google Cloud Platform account
- Azure OpenAI account
- Zilliz Cloud account

### **Installation**

1. **Clone the repository**
```bash
git clone https://github.com/your-org/healthnavi-ai-cdss.git
cd healthnavi-ai-cdss
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment Configuration**
```bash
cp .env.example .env
# Edit .env with your configuration
```

### **Required Environment Variables**

```bash
# Security
SECRET_KEY=your-super-secure-secret-key-min-32-chars
ENCRYPTION_KEY=your-encryption-key-min-32-chars

# Database
DB_USER=healthnavi_user
DB_PASSWORD=your-secure-db-password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=healthnavi_cdss

# Google Cloud / Vertex AI
GCP_ID=your-gcp-project-id
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-openai-key
API_VERSION=2024-02-01
DEPLOYMENT=text-embedding-3-large

# Zilliz/Milvus
MILVUS_URI=https://your-cluster.zillizcloud.com
MILVUS_TOKEN=your-milvus-token
MILVUS_COLLECTION_NAME=medical_knowledge

# AWS S3
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
AWS_S3_BUCKET=healthnavi-cdss

# Application
ENV=production
DEBUG=false
LOG_LEVEL=INFO
CORS_ORIGINS=["https://your-frontend-domain.com"]
```

### **Database Setup**

1. **Create database**
```bash
createdb healthnavi_cdss
```

2. **Run migrations**
```bash
alembic upgrade head
```

### **Docker Deployment**

```bash
# Build and start services
docker-compose up -d

# Check logs
docker-compose logs -f api

# Stop services
docker-compose down
```

## 🏗️ Architecture

### **System Architecture**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   PostgreSQL    │
│   (React/Vue)   │◄──►│   Backend       │◄──►│   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Vector Store  │
                       │   (Zilliz)      │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   AI Models     │
                       │   (Vertex AI)   │
                       └─────────────────┘
```

### **Security Layers**
1. **Network Security**: HTTPS, CORS, Security Headers
2. **Application Security**: Authentication, Authorization, Input Validation
3. **Data Security**: Encryption, Audit Logging, PHI Protection
4. **Infrastructure Security**: Container Security, Secrets Management

## 📚 API Documentation

### **Authentication Endpoints**

#### **Register User**
```http
POST /api/v2/auth/register
Content-Type: application/json

{
  "username": "doctor_smith",
  "email": "doctor@hospital.com",
  "password": "SecurePassword123!",
  "full_name": "Dr. John Smith"
}
```

#### **Login**
```http
POST /api/v2/auth/login
Content-Type: application/json

{
  "username": "doctor_smith",
  "password": "SecurePassword123!"
}
```

#### **Refresh Token**
```http
POST /api/v2/auth/refresh
Content-Type: application/json

{
  "refresh_token": "your-refresh-token"
}
```

### **Diagnosis Endpoints**

#### **Generate Diagnosis**
```http
POST /api/v2/diagnosis/diagnose
Authorization: Bearer your-access-token
Content-Type: application/json

{
  "patient_data": "65-year-old male with chest pain, shortness of breath",
  "chat_history": "Previous conversation...",
  "session_id": "session-uuid"
}
```

#### **Get Diagnosis Sessions**
```http
GET /api/v2/diagnosis/sessions
Authorization: Bearer your-access-token
```

### **System Endpoints**

#### **Health Check**
```http
GET /api/v2/health
```

## 🧪 Testing

### **Run Tests**
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run security tests
pytest -m security

# Run integration tests
pytest -m integration
```

### **Test Coverage**
- **Unit Tests**: >90% coverage
- **Integration Tests**: Critical user flows
- **Security Tests**: Authentication, authorization, data protection
- **Performance Tests**: Load testing, stress testing

## 🔧 Development

### **Code Quality**
```bash
# Format code
black app/
isort app/

# Lint code
flake8 app/
mypy app/

# Security scan
bandit -r app/
safety check
```

### **Pre-commit Hooks**
```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## 📊 Monitoring & Logging

### **Logging**
- **Structured Logging**: JSON-formatted logs
- **PHI Sanitization**: Automatic PHI removal from logs
- **Audit Logging**: Complete audit trail
- **Security Events**: Security event tracking

### **Monitoring**
- **Health Checks**: Comprehensive health monitoring
- **Performance Metrics**: Response times, throughput
- **Security Metrics**: Failed logins, suspicious activity
- **Error Tracking**: Error rates and patterns

## 🚨 Security Considerations

### **Production Deployment**
1. **Use HTTPS**: Always use HTTPS in production
2. **Secure Secrets**: Use proper secrets management
3. **Network Security**: Configure firewalls and VPCs
4. **Regular Updates**: Keep dependencies updated
5. **Security Scanning**: Regular security scans

### **Compliance**
- **HIPAA**: Implement required safeguards
- **GDPR**: Data protection and privacy controls
- **SOC 2**: Security and availability controls
- **ISO 13485**: Quality management system

### **Incident Response**
1. **Security Incident Plan**: Documented response procedures
2. **Audit Logs**: Complete audit trail for investigations
3. **Data Breach Procedures**: GDPR/HIPAA breach notification
4. **Recovery Procedures**: Data backup and recovery

## 🤝 Contributing

### **Security Guidelines**
1. **Security Review**: All code changes require security review
2. **Vulnerability Reporting**: Report security issues responsibly
3. **Code Standards**: Follow security coding standards
4. **Testing**: Comprehensive security testing required

### **Development Process**
1. **Fork Repository**: Create feature branch
2. **Security Scan**: Run security scans
3. **Code Review**: Security-focused code review
4. **Testing**: Comprehensive testing
5. **Documentation**: Update security documentation

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### **Security Issues**
- **Email**: security@healthnavi.com
- **PGP Key**: Available on request
- **Response Time**: 24 hours for critical issues

### **General Support**
- **Documentation**: [docs.healthnavi.com](https://docs.healthnavi.com)
- **Issues**: GitHub Issues
- **Community**: Discord Server

## 🔗 Links

- **Documentation**: [docs.healthnavi.com](https://docs.healthnavi.com)
- **API Reference**: [api.healthnavi.com/docs](https://api.healthnavi.com/docs)
- **Security Policy**: [SECURITY.md](SECURITY.md)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---

**⚠️ Important**: This is medical software. Always ensure proper testing and validation before clinical use. Follow all applicable regulations and standards.