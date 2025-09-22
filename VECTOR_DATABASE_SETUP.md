# Vector Database Setup Guide for HealthNavi AI CDSS

## Overview
This guide will help you configure your vector database (Zilliz Cloud/Milvus) to provide medical knowledge context to the AI model.

## Current Status
✅ **Vector Database Service Created**: `backend/src/healthnavi/services/vectordb_service.py`
✅ **Environment Variables Added**: Updated `docker-compose.yml` with all required variables
✅ **Dependencies Installed**: `pymilvus` and `requests` are in `requirements.txt`

## Required Configuration

### 1. Create .env File
Create a `.env` file in your project root with these variables:

```bash
# Zilliz Cloud / Milvus Configuration
MILVUS_URI=https://your-cluster-id.zillizcloud.com
MILVUS_TOKEN=your-zilliz-token
MILVUS_DB_NAME=default
MILVUS_COLLECTION_NAME=medical_knowledge
MILVUS_DRUG_COLLECTION_NAME=drug_knowledge

# Azure OpenAI Configuration (for embeddings)
AZURE_OPENAI_API_KEY=your-azure-openai-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_REGION=eastus
MODEL_NAME=text-embedding-3-large
DEPLOYMENT=text-embedding-3-large
API_VERSION=2024-02-01

# AWS S3 Configuration (if using S3)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
AWS_S3_BUCKET=your-s3-bucket-name
```

### 2. Zilliz Cloud Setup
1. **Sign up**: Go to https://cloud.zilliz.com/
2. **Create Cluster**: Create a new cluster
3. **Get Credentials**: 
   - Copy your cluster URI (MILVUS_URI)
   - Generate an API token (MILVUS_TOKEN)
4. **Create Collections**:
   - `medical_knowledge` - for medical knowledge base
   - `drug_knowledge` - for drug information

### 3. Azure OpenAI Setup (for embeddings)
1. **Create Resource**: Set up Azure OpenAI resource
2. **Deploy Model**: Deploy `text-embedding-3-large` model
3. **Get Credentials**:
   - API Key (AZURE_OPENAI_API_KEY)
   - Endpoint URL (AZURE_OPENAI_ENDPOINT)

### 4. Data Upload
You'll need to upload your medical knowledge data to the collections. The service expects these fields:

**medical_knowledge collection**:
- `embedding` (vector field)
- `text` (medical knowledge text)
- `source` (source reference)
- `metadata` (additional metadata)

**drug_knowledge collection**:
- `embedding` (vector field)
- `drug_name` (drug name)
- `description` (drug description)
- `indications` (medical indications)
- `contraindications` (contraindications)
- `dosage` (dosage information)
- `side_effects` (side effects)

## Testing the Setup

### 1. Restart Containers
```bash
docker compose down
docker compose up -d
```

### 2. Check Logs
```bash
docker compose logs api --tail 20
```

Look for these messages:
- ✅ `"Loaded real ZillizService from vectordb_service"`
- ✅ `"Connected to Zilliz Cloud database: default"`
- ✅ `"Loaded collection: medical_knowledge"`
- ✅ `"Loaded collection: drug_knowledge"`

### 3. Test Diagnosis API
```bash
curl -X POST http://localhost:8050/api/v2/diagnosis/diagnose \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_data": "Patient complains of chest pain and shortness of breath",
    "chat_history": ""
  }'
```

## Troubleshooting

### Common Issues:

1. **"Zilliz/Milvus configuration not found"**
   - Check that MILVUS_URI and MILVUS_TOKEN are set in .env
   - Restart containers after updating .env

2. **"Failed to connect to Zilliz Cloud"**
   - Verify MILVUS_URI format: `https://your-cluster-id.zillizcloud.com`
   - Check MILVUS_TOKEN is valid
   - Ensure cluster is running

3. **"Collection not found"**
   - Create collections in Zilliz Cloud console
   - Use exact names: `medical_knowledge` and `drug_knowledge`

4. **"Failed to get embedding"**
   - Check Azure OpenAI configuration
   - Verify API key and endpoint
   - Ensure model is deployed

5. **"No vector store available"**
   - Check all environment variables are set
   - Verify network connectivity
   - Check logs for specific errors

## Expected Behavior

### With Vector Database:
- AI responses include medical knowledge context
- Responses reference specific medical sources
- Drug information is included when relevant

### Without Vector Database:
- AI works with its training data only
- No medical knowledge context
- Still provides helpful responses

## Next Steps

1. **Set up your .env file** with actual credentials
2. **Create Zilliz Cloud account** and cluster
3. **Set up Azure OpenAI** for embeddings
4. **Upload your medical data** to the collections
5. **Test the diagnosis API** to verify RAG is working

The system will work without the vector database, but with it, you'll get much more accurate and contextually relevant medical responses!
