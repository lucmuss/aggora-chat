# Test Accounts

These accounts are seeded by `python manage.py seed` and by the container startup flow when `AUTO_SEED_ON_START=1`.

## Demo Users

| Role | Email | Password | Handle |
| --- | --- | --- | --- |
| Demo user | `ariane.keller01@mailseed.test` | `SeedPass!2026` | `ariane_keller` |
| Demo user | `jonas.hartmann02@mailseed.test` | `SeedPass!2026` | `jonas_hartmann` |
| Demo user | `mila.neumann03@mailseed.test` | `SeedPass!2026` | `mila_neumann` |
| Demo user | `leon.wagner04@mailseed.test` | `SeedPass!2026` | `leon_wagner` |
| Demo user | `sophie.brandt05@mailseed.test` | `SeedPass!2026` | `sophie_brandt` |

## Admin Accounts

| Role | Email | Password | Handle |
| --- | --- | --- | --- |
| Superuser admin | `ops-admin@aggora.app` | `AdminPass!2026` | `ops_admin` |
| Moderator admin | `ops-moderator@aggora.app` | `ModeratorPass!2026` | `ops_moderator` |

## Notes

- Seed source files live in `data/seed/users.json` and `data/seed/admins.json`.
- The demo community is `c/freya-seed-lounge`.
- The moderator account is added to the seed community as a moderator.
- The superuser admin is added to the seed community as an owner.
