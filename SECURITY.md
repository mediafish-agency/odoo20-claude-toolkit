# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub: on this repository, open the **Security** tab and
choose **Report a vulnerability**. Do not open a public issue for a security problem.

Useful reports include the affected version, the tool or hook involved, and steps to reproduce.

## Scope

In scope: anything that lets the plugin, its MCP server or its hooks get around the
[safety model](docs/safety.md). For example: writing inside the Odoo source tree, touching a database outside
`db_allow`, committing without `allow_writes`, calling a non-read method through `odoo_live_call` without
`allow_writes`, exposing a server beyond 127.0.0.1, or leaking the API key or a database password.

Out of scope: vulnerabilities in Odoo itself (report them to Odoo S.A.:
<https://www.odoo.com/security-report>), and in Claude Code or the MCP SDK (report them to their maintainers).

## Supported versions

Only the latest release receives fixes.
