# Hermes Newsroom

Hermes Newsroom is a local, single-user Hermes plugin that researches configured Topics, consolidates related reporting into evidence-aware Stories, and provides a compact review queue in the Hermes Dashboard.

The canonical product contract is [the v1.1 specification](plan/Hermes_Newsroom_—_Full_Product_and_Implementation_Specification_v1.1.md). [BUILD_PLAN.md](plan/BUILD_PLAN.md) records the Hermes-runtime adaptation.

## Development

```powershell
python -m pytest -q
npm ci
npm run typecheck
npm run build
pwsh -File scripts\install_plugin.ps1 -Profile newsroom-dev
pwsh -File scripts\verify.ps1 -Profile newsroom-dev -RequireCron
```

All live commands require an explicit profile. Runtime data is never stored in this repository.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Installation](docs/INSTALL.md)
- [Operations](docs/OPERATIONS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Implementation report](docs/IMPLEMENTATION_REPORT.md)
