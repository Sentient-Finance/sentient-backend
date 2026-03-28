## Summary

<!-- Briefly describe what this PR does and why -->

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Refactor
- [ ] Documentation
- [ ] Infrastructure (Docker Compose, CI, migrations)

## Areas Affected

- [ ] `apps/api`
- [ ] `apps/worker`
- [ ] `apps/indexer`
- [ ] `libs/core`
- [ ] `libs/chain`
- [ ] `libs/db`
- [ ] `infra`
- [ ] `alembic`

## Related Issue

<!-- Link issue: Fixes #123 -->

## Technical Details

- [ ] Migration added (run `make revision MSG="..."` then `make migrate`)
- [ ] Docker Compose config changed
- [ ] New environment variable added (update `.env.example`)
- [ ] Chainlink/CCIP integration changed
- [ ] New Celery task added

## Testing

- [ ] `make test` passes locally
- [ ] Manual API testing (endpoints: `/api/v1/health`, `/api/v1/ready`, `/api/v1/vaults`, etc.)
- [ ] Worker/Indexer tested if affected

## Evidence (Optional)

<details>
<summary>Logs / Screenshots</summary>

<!-- Paste relevant output -->

</details>

## Checklist

- [ ] `make lint` passes
- [ ] `make format` applied
- [ ] `make test` passes
- [ ] Migration is reversible (`make downgrade`)
- [ ] `.env.example` updated if new env vars added
