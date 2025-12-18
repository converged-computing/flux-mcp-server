# flux-mcp server

> 🌀 Service to deploy functions for MCP tools for Flux Framework

This library uses [flux-mcp](https://github.com/converged-computing/flux-mcp)
![img/flux-mcp-small.png](img/flux-mcp-small.png)

## Usage

This server is currently expected to be deployed on a cluster, alongside a Flux instance.
This means you need flux-python (comes packaged with Flux, or `pip install flux-python==<version>`).

### Server

To start the demo server, either will work:

```bash
flux-mcp-server
# or
python3 -m flux_mcp_server.server
```

![img/server.png](img/server.png)

### Development

```bash
apt-get install -y python3-build
pyproject-build
```

### Todo

- [x] Fastmcp endpoint serving Flux MCP functions
- [ ] Handle should receive events and write to database
- [ ] Database should be interface (and flexible to different ones)
  - sqlalchemy
- [ ] Auth should also be interface with different backends
  - Most basic is "none" that just uses the Flux handle.
  - Next is simple token, should be implemented as middleware of fastmcp
  - Then OAuth2
  - Then (custom) something with passing OAuth2-like to submit as a Flux user.
- [ ] Example: user manually submits a job, can query database for state
- [ ] Example: Agent submits work, and can find state later.
- Migrate to container, then Flux Operator / Kubernetes service.

## License

HPCIC DevTools is distributed under the terms of the MIT license.
All new contributions must be made under this license.

See [LICENSE](https://github.com/converged-computing/cloud-select/blob/main/LICENSE),
[COPYRIGHT](https://github.com/converged-computing/cloud-select/blob/main/COPYRIGHT), and
[NOTICE](https://github.com/converged-computing/cloud-select/blob/main/NOTICE) for details.

SPDX-License-Identifier: (MIT)

LLNL-CODE- 842614
