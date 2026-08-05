# RDS — Managed PostgreSQL Database

## What It Is

Amazon RDS is a managed PostgreSQL service. AWS runs the database server for you. It handles backups, patches, and availability. You connect to it like any other PostgreSQL database.

## Why Use It

This app needs PostgreSQL. You can run it yourself (local Docker, your own server) or use RDS. RDS is the production choice because:
- AWS handles backups and updates
- You can scale compute and storage independently
- Multi-AZ option keeps database running during failures
- Monitoring and alerts are built in

## Setup Steps

### Step 1: Create RDS Instance

In AWS Console:
1. Go to RDS service
2. Click "Create database"
3. Choose "Standard create"
4. Engine: PostgreSQL
5. Version: 15 or 16 (matches your app)
6. Templates: Free tier or Production
7. DB instance identifier: `fastapi-db`
8. Master username: `postgres`
9. Master password: set a strong password
10. Connectivity: choose your VPC, enable public access if connecting from outside VPC
11. Security group: allow port 5432 from your app server
12. Initial database name: `fastapi_app`
13. Click "Create database"

Wait 5–10 minutes for AWS to provision it.

### Step 2: Get Connection Details

After creation, AWS gives you:
- **Endpoint**: `fastapi-db.xxxxxx.region.rds.amazonaws.com`
- **Port**: `5432`
- **Database name**: `fastapi_app`
- **Username**: `postgres`
- **Password**: what you set

### Step 3: Configure the App

In your `.env` file:

```env
RDS_ENDPOINT=fastapi-db.xxxxxx.region.rds.amazonaws.com
RDS_DB_NAME=fastapi_app
RDS_USERNAME=postgres
RDS_PASSWORD=your-password
RDS_PORT=5432
```

Or set `DATABASE_URL` directly:

```env
DATABASE_URL=postgresql+asyncpg://postgres:your-password@fastapi-db.xxxxxx.region.rds.amazonaws.com:5432/fastapi_app
```

### Step 4: Run Database Migrations

```bash
alembic upgrade head
```

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `RDS_ENDPOINT` | RDS hostname | `fastapi-db.xxxxxx.region.rds.amazonaws.com` |
| `RDS_DB_NAME` | Database name | `fastapi_app` |
| `RDS_USERNAME` | Login user | `postgres` |
| `RDS_PASSWORD` | Login password | `secure-password` |
| `RDS_PORT` | Connection port | `5432` |
| `DATABASE_URL` | Full connection string (alternative) | `postgresql+asyncpg://...` |

## Connection Pool Settings

When using RDS, the app uses special pool settings for RDS. These are separate from the local PostgreSQL settings.

```env
# RDS pool settings
RDS_POOL_SIZE=20
RDS_MAX_OVERFLOW=40
RDS_POOL_TIMEOUT=30
RDS_POOL_RECYCLE=1800
RDS_POOL_PRE_PING=true
```

| Setting | Purpose | Default for RDS | Default for Local |
|---------|---------|-----------------|-------------------|
| `RDS_POOL_SIZE` | Number of connections kept open in the pool | `20` | `10` |
| `RDS_MAX_OVERFLOW` | Extra connections allowed when pool is full | `40` | `20` |
| `RDS_POOL_TIMEOUT` | Seconds to wait for a connection before error | `30` | `30` |
| `RDS_POOL_RECYCLE` | Max age of a connection in seconds (`1800` = 30 minutes) | `1800` | off |
| `RDS_POOL_PRE_PING` | Test connection is alive before using it | `true` | `true` |

### What Each Setting Does

**Pool Size**
How many database connections the app keeps ready. If your app has 4 worker processes and each needs 5 connections, set this to `20` or higher.

**Max Overflow**
Extra connections allowed beyond pool size when all workers are busy. These are created temporarily and closed after use.

**Pool Timeout**
How long a request waits for a free connection before raising an error. Increase this if you see timeout errors under load.

**Pool Recycle**
How long a connection can live before being replaced. RDS closes idle connections after some time. Recycling prevents "connection closed" errors. `1800` seconds = 30 minutes is a safe default.

**Pool Pre Ping**
Before using a connection, send a small check to the database. If the connection is dead, get a new one. This adds a tiny bit of overhead but prevents errors.

### Choosing Values

For small apps:
```env
RDS_POOL_SIZE=10
RDS_MAX_OVERFLOW=20
```

For medium apps:
```env
RDS_POOL_SIZE=20
RDS_MAX_OVERFLOW=40
```

For large apps:
```env
RDS_POOL_SIZE=50
RDS_MAX_OVERFLOW=100
```

Make sure the total possible connections does not exceed your RDS limit. Check your RDS instance's max connections setting in AWS Console.

### Monitoring Connections

Watch these in CloudWatch:
- `DatabaseConnections` - current open connections
- `ConnectionCount` - new connections per second

If you see `too many connections` errors, lower `RDS_POOL_SIZE` or increase the RDS instance's connection limit.

## Security

### VPC

Best practice: put RDS inside a private VPC subnet. Your app (ECS/EKS/EC2) connects through VPC, not public internet.

### Security Groups

Allow only:
- Port `5432`
- Source: your app server's security group or IP

Block:
- Public internet access (unless absolutely needed)

### Secrets Manager (Recommended)

Don't put `RDS_PASSWORD` in `.env`. Store it in AWS Secrets Manager and fetch at runtime.

See `secrets-manager-guide.md` for details.

### IAM Authentication (Optional)

RDS supports IAM database authentication. Instead of password, use AWS IAM credentials. More complex, but no password to manage.

## Backups

RDS automatically creates backups:
- **Automated backups**: daily, kept 7–35 days
- **Transaction logs**: point-in-time recovery
- **Snapshots**: manual, kept indefinitely

Configure in RDS settings.

## SSL Connection

For production, enforce SSL:

```python
DATABASE_URL=postgresql+asyncpg://user:pass@endpoint:5432/db?ssl=require
```

## Common Operations

### Connect with psql

```bash
psql -h fastapi-db.xxxxxx.region.rds.amazonaws.com -U postgres -d fastapi_app
```

### Check Connection

```bash
PGPASSWORD=your-password psql -h endpoint -U postgres -c "SELECT version();"
```

### Monitor in CloudWatch

RDS sends metrics to CloudWatch:
- CPU utilization
- Database connections
- Read/write latency
- Free storage space

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` | Security group blocks port 5432 | Allow port in RDS security group |
| `Timeout` | RDS not publicly accessible or wrong endpoint | Check endpoint, enable public access or use VPC |
| `Authentication failed` | Wrong username/password | Reset master password in RDS |
| `Database does not exist` | DB not created during setup | Recreate RDS instance with correct name |

## RDS vs Local PostgreSQL

| Feature | RDS | Local |
|---------|-----|-------|
| Setup | AWS handles it | You install and maintain |
| Backups | Automatic | Manual or Docker volumes |
| Scaling | Change instance size/storage | Migrate to bigger server |
| High availability | Multi-AZ option | You set up replication |
| Cost | Pay per hour + storage | Free (if you have server) |
| Speed | Depends on instance | Local is faster |

## Next Steps

- Read `secrets-manager-guide.md` to store credentials safely
- Read `aws-architecture.md` for how RDS fits with other services
- Read `cloudwatch-guide.md` to monitor database performance

---

← Back to [Docs Index](README.md) · Next: [DynamoDB Guide](dynamodb-guide.md)
