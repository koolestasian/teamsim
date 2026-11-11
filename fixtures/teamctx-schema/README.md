# teamctx store schema (pinned copy)

The SQLite migrations of [teamctx](https://github.com/koolestasian/discord-team-context),
copied from `crates/teamctx-store/migrations` at commit `cd8cc26`. The prototype's checker
reads teamctx's database read-only, and its unit tests build a database from these files.

When teamctx adds a migration, copy it here in the same commit that updates the checker.
