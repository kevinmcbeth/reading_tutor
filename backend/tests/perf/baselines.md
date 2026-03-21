# Performance Baselines

Target latencies for the reading tutor API running with mock services.

| Category | p50 | p95 | p99 |
|---|---|---|---|
| Health | <5ms | <10ms | <20ms |
| Auth (register/login) | <50ms | <100ms | <200ms |
| Story list/detail | <50ms | <120ms | <250ms |
| Session CRUD | <30ms | <80ms | <150ms |
| Asset serving (image/audio) | <20ms | <50ms | <100ms |
| Speech recognition (mock) | <20ms | <50ms | <100ms |
| Analytics | <50ms | <150ms | <300ms |

## Notes

- These targets assume mock services (no GPU operations).
- Measured with 10 concurrent users, spawn rate 2/s, 60s run.
- Database: local PostgreSQL with seeded test data.
- Deviations from these baselines indicate regressions in application code or database queries.
