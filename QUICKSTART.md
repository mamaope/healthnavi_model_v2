# 🚀 HealthNavi AI CDSS - Quick Start Guide

## ✅ Environment Setup Complete!

Your environment has been configured with secure defaults. Here's what you need to do next:

## 🔧 **Step 1: Update API Keys (Required)**

Edit the `.env` file and update these critical values:

```bash
# Google Cloud / Vertex AI
GCP_ID=your-actual-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account.json

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-actual-azure-openai-key

# Zilliz/Milvus Vector Database
MILVUS_URI=https://your-cluster.zillizcloud.com
MILVUS_TOKEN=your-actual-milvus-token

# AWS S3
AWS_ACCESS_KEY_ID=your-actual-aws-access-key
AWS_SECRET_ACCESS_KEY=your-actual-aws-secret-key
```

## 🐳 **Step 2: Start the Application**

```bash
# Start all services (backend, frontend, and database)
docker-compose up -d

# Check backend logs
docker-compose logs -f api

# Check frontend logs
docker-compose logs -f frontend

# Check database logs
docker-compose logs -f db
```

## 🔍 **Step 3: Verify Installation**

1. **Frontend Application**: http://localhost:3000
2. **Backend Health Check**: http://localhost:8050/health
3. **API Documentation**: http://localhost:8050/docs
4. **Database**: PostgreSQL on localhost:5432

## 🧪 **Step 4: Test the API**

### Register a User
```bash
curl -X POST "http://localhost:8050/api/v2/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "doctor_test",
    "email": "doctor@test.com",
    "password": "SecurePassword123!",
    "full_name": "Dr. Test User"
  }'
```

### Login
```bash
curl -X POST "http://localhost:8050/api/v2/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "doctor_test",
    "password": "SecurePassword123!"
  }'
```

### Make a Diagnosis Request
```bash
curl -X POST "http://localhost:8050/api/v2/diagnosis/diagnose" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "patient_data": "65-year-old male with chest pain and shortness of breath",
    "chat_history": "",
    "session_id": "test-session-123"
  }'
```

## 🛠️ **Development Mode**

For development with hot reloading:

```bash
# Install dependencies locally
pip install -r requirements.txt

# Run locally (without Docker)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8050
```

## 🔒 **Security Features Active**

✅ **Authentication**: JWT-based with refresh tokens  
✅ **Rate Limiting**: Protection against brute force attacks  
✅ **Input Validation**: Comprehensive data sanitization  
✅ **PHI Encryption**: AES-256 encryption for sensitive data  
✅ **Audit Logging**: Complete audit trail  
✅ **CORS Protection**: Secure cross-origin requests  

## 📊 **Monitoring**

- **Health Check**: `/health` endpoint
- **Logs**: Available in `./logs/` directory
- **Database**: PostgreSQL with health checks
- **Metrics**: Built-in performance monitoring

## 🚨 **Troubleshooting**

### Common Issues:

1. **Database Connection Failed**
   ```bash
   # Check database status
   docker-compose logs db
   
   # Restart database
   docker-compose restart db
   ```

2. **API Keys Not Working**
   - Verify all API keys in `.env` file
   - Check service account JSON file path
   - Ensure APIs are enabled in cloud consoles

3. **Port Conflicts**
   ```bash
   # Check what's using port 8050
   netstat -ano | findstr :8050
   
   # Change port in docker-compose.yml if needed
   ```

4. **Permission Issues**
   ```bash
   # Fix log directory permissions
   chmod 755 logs/
   ```

## 📚 **Next Steps**

1. **Configure Production Environment**
   - Update `ENV=production` in `.env`
   - Set `DEBUG=false`
   - Configure production CORS origins
   - Set up HTTPS

2. **Set Up Monitoring**
   - Configure log aggregation
   - Set up alerting
   - Monitor security events

3. **Data Ingestion**
   - Upload medical documents to S3
   - Run data ingestion scripts
   - Verify vector store population

## 🆘 **Need Help?**

- **Documentation**: Check `README.md` for detailed information
- **Security**: Review `SECURITY.md` for security policies
- **Issues**: Create GitHub issues for bugs
- **Support**: Contact security@healthnavi.com for security issues

---

**🎉 Congratulations! Your HealthNavi AI CDSS is now running securely!**
