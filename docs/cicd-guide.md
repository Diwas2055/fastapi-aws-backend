# CI/CD Guide for FastAPI AWS Backend

## What is CI/CD?

CI/CD is a way to automate testing, building, and deploying your code. Instead of manually running tests and deploying, GitHub Actions does it for you every time you push code.

### CI (Continuous Integration)

Every time you push code, GitHub automatically:
- Installs dependencies
- Runs tests
- Checks code quality (linting, type checking)
- Builds the Docker image

If anything fails, you get notified immediately.

### CD (Continuous Deployment)

When code passes all checks and you merge to `main`, GitHub automatically:
- Pushes the Docker image to a registry
- Deploys to your server or AWS
- Runs post-deployment health checks

---

## Why Use CI/CD?

- **Catch bugs early**: Tests run on every push, not just before deployment
- **No more "it works on my machine"**: Same process runs for everyone
- **Save time**: No manual testing or deployment steps
- **Consistent deployments**: Same process every time
- **Fast feedback**: Know within minutes if something is broken

---

## How It Works for This Project

```
Push code → GitHub Actions triggers → Runs tests → Builds image → Deploys
```

### Workflow for a New Feature

1. You create a branch: `git checkout -b feature/add-user-api`
2. You push code: `git push origin feature/add-user-api`
3. GitHub Actions runs automatically:
   - Lint check
   - Type check
   - Tests
   - Docker build
4. If all pass, you create a Pull Request
5. When PR is merged to `main`, deployment runs automatically

---

## CI/CD Concepts Explained Simply

### `needs`

Makes one job wait for another job to finish first.

```yaml
jobs:
  deploy:
    needs: [test, lint]   # deploy waits for test AND lint to pass
```

Use this when job B depends on job A. Example: deployment should wait for tests.

---

### `if`: Conditions

Run a job only when a condition is true.

```yaml
deploy:
  if: github.ref == 'refs/heads/main'   # only run on main branch
```

Common conditions:
- `github.ref == 'refs/heads/main'` — run only on main branch
- `github.event_name == 'push'` — run only on push events
- `github.event.pull_request.merged == true` — run only after PR merge

---

### `always()`

Run a job even if previous jobs failed.

```yaml
notify:
  if: always()    # always run, even if tests failed
```

Use this for cleanup, sending notifications, or uploading logs.

---

### `failure()`

Run a job only when a previous job fails.

```yaml
alert-on-failure:
  if: failure()   # only run if any previous job failed
```

Use this for rollback or sending alerts when something breaks.

---

### `strategy.matrix`

Run the same job multiple times with different settings.

```yaml
test:
  strategy:
    matrix:
      python-version: ["3.11", "3.12", "3.13"]
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
```

This runs the test job 3 times — once for each Python version.

---

### `fail-fast`

Stop all matrix jobs if one fails.

```yaml
test:
  strategy:
    fail-fast: true    # stop remaining jobs if one fails
    matrix:
      os: [ubuntu, macos, windows]
```

Use this to save time and GitHub Actions minutes.

---

### `max-parallel`

Control how many matrix jobs run at the same time.

```yaml
test:
  strategy:
    max-parallel: 2    # run at most 2 jobs at once
    matrix:
      python-version: ["3.11", "3.12", "3.13", "3.14"]
```

Use this when your infrastructure or licenses limit parallel execution.

---

### `run` vs `uses`

Two ways to execute commands in a step:

**`run`** — Execute shell commands directly.

```yaml
- run: pytest tests/
- run: ruff check .
```

**`uses`** — Reuse an existing action (pre-built workflow).

```yaml
- uses: actions/checkout@v4      # checks out your code
- uses: actions/setup-python@v5  # installs Python
```

Use `uses` for common tasks. Use `run` for commands specific to your project.

---

### Expression Functions

Small helper functions to make conditions smarter.

```yaml
# Check if branch name starts with "release/"
if: startsWith(github.ref_name, 'release/')

# Check if tag starts with "v"
if: startsWith(github.ref_name, 'v')

# Check if branch contains "feature"
if: contains(github.ref_name, 'feature')

# Build image tag from branch name
run: echo "TAG=${{ github.ref_name }}" >> $GITHUB_ENV
```

Available functions: `startsWith()`, `endsWith()`, `contains()`, `format()`

---

### Secrets & Variables

Store sensitive data securely. Never hardcode credentials.

**Secrets** (for sensitive data like passwords, API keys):
```yaml
- run: echo "${{ secrets.DATABASE_PASSWORD }}"
```

**Variables** (for non-sensitive config):
```yaml
- run: echo "${{ vars.AWS_REGION }}"
```

Set them in GitHub: Repository → Settings → Secrets and variables → Actions

---

## Workflows in This Project

### `.github/workflows/ci.yml`

Runs on every push and pull request:
- Lint check (ruff)
- Type check (mypy)
- Tests (pytest)
- Docker build check

### `.github/workflows/deploy.yml`

Runs only when code is merged to `main`:
- Build and push Docker image to registry
- Deploy to production server
- Run health check after deployment

---

## Setting Up Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets for deployment:

| Secret | Description |
|--------|-------------|
| `DOCKER_REGISTRY` | Docker registry URL (e.g., docker.io/username) |
| `DOCKER_USERNAME` | Docker registry username |
| `DOCKER_PASSWORD` | Docker registry password |
| `SSH_PRIVATE_KEY` | SSH key for connecting to production server |
| `SSH_HOST` | Production server IP or hostname |
| `SSH_USER` | SSH username (e.g., ubuntu, ec2-user) |
| `AWS_ACCESS_KEY_ID` | AWS access key for deployment |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for deployment |
| `AWS_REGION` | AWS region (e.g., us-east-1) |

---

## Workflow Status Badge

Add this to your `README.md` to show CI status:

```markdown
![CI](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci.yml/badge.svg)
```

---

## Common Commands

```bash
# View workflow runs
gh run list

# View specific run logs
gh run view <run-id>

# Re-run a failed run
gh run rerun <run-id>
```
