# Security Notes

FraudOps is built for local development with generated banking data. The repository should not contain real customer data, production credentials, private keys, or cloud access tokens.

## Current Controls

- Synthetic data only
- Masked card numbers in generated data
- Environment variable support for database connection settings
- `.env` files ignored by git
- Local API request validation through Pydantic
- SQLAlchemy and parameterized SQL patterns in API code
- Analyst actions recorded in case history
- Model, rule, and threshold metadata tracked in configuration and database tables
- Generated data, local databases, dependency folders, model binaries, and build outputs ignored by git

## Local Development Credentials

The project includes placeholder PostgreSQL credentials for local Docker development. Replace them before any shared or hosted deployment.

## Before Cloud Deployment

- Rotate all local credentials
- Store secrets outside git
- Add role-based application permissions
- Add authentication and authorization to the API and analyst console
- Move API state from SQLite to PostgreSQL
- Enable structured audit logging for user actions
- Block public S3 access
- Use least-privilege IAM policies
- Send application and infrastructure logs to CloudWatch

