# HealthNavi AI CDSS - Quick API Reference

## Base URL
```
http://localhost:8050/api/v2
```

## Authentication Flow
```bash
# 1. Register
curl -X POST http://localhost:8050/api/v2/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe", 
    "email": "john@example.com",
    "password": "SecurePass123!"
  }'

# 2. Verify Email (click link in email or use manual verify)
curl -X POST http://localhost:8050/api/v2/auth/manual-verify \
  -H "Content-Type: application/json" \
  -d '"john@example.com"'

# 3. Login
curl -X POST http://localhost:8050/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePass123!"
  }'

# 4. Use token for authenticated requests
curl -X POST http://localhost:8050/api/v2/diagnosis/diagnose \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Patient has chest pain",
    "patient_data": {
      "age": 45,
      "gender": "male"
    }
  }'
```

## Common Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login with email/password (returns profile)
- `GET /auth/profile` - Get current user profile
- `GET /auth/verify-email?token=X` - Verify email (click link)
- `POST /auth/resend-verification` - Resend verification email
- `POST /auth/manual-verify` - Manual verify (dev only)

### User Management (Admin)
- `GET /auth/users` - List all users
- `GET /auth/users/{id}` - Get user by ID

### Diagnosis
- `POST /diagnosis/diagnose` - Generate AI diagnosis
- `GET /diagnosis/health` - Check AI service status

### System
- `GET /health` - Application health check

## Response Format
```json
{
  "data": { /* response data */ },
  "metadata": {
    "statusCode": 200,
    "errors": [],
    "executionTime": 0.123,
    "timestamp": "2025-09-22T10:30:00.000000"
  },
  "success": 1
}
```

## User Roles
- `user` - Basic access
- `admin` - User management
- `super_admin` - Full access

## Error Codes
- `200` - Success
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `500` - Server Error
- `503` - Service Unavailable
