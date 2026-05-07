# HaC Service Catalog

Canonical location for the HaC service topology model.

## Files

- `development/service-catalog/schema/service-catalog.schema.json` - Versioned schema for catalog structure.
- `development/service-catalog/data/services.catalog.json` - Service catalog data.
- `scripts/validate_service_catalog.ps1` - Validation script for schema metadata, required fields, path integrity, and dependency references.

## Validate

```powershell
pwsh -NoProfile -File ./scripts/validate_service_catalog.ps1
```

## Generate Inventory

```powershell
pwsh -NoProfile -File ./scripts/generate_service_catalog_inventory.ps1
```

This regenerates `services.inventory.json` from active `deploy-*.yml` workflows and infers baseline metadata for every managed stack.

## Sync Catalog Coverage

```powershell
pwsh -NoProfile -File ./scripts/sync_service_catalog.ps1
```

This expands the canonical catalog to full workflow coverage while preserving curated metadata that already exists in `services.catalog.json`.

## Notes

- Keep `id` stable once introduced.
- Add dependencies by `id` only.
- Ensure every `composePath` and `workflowPath` points to a real file.
- Run inventory generation and sync before validation when new deploy workflows are added.
