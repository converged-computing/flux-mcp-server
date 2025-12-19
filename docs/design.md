# Design

flux-mcp-server has an interesting design pattern because normally MCP functions are stateless, but when we
introduce a Flux handle (or events listener) it becomes stateful. Here is how I am thinking about
that separation:

- **flux_mcp**: provides the functions (tools) and is stateless. It wraps the Flux API and any function can accept a handle abstraction. It doesn't care about state and does not depend on it.
- **flux_mcp_server**: is the application. It has state, configuration, and databsae definitions. E.g., the server can receive updates in the form of events and write to a databsae for agents to access. It uses functions from `flux_mcp` and provides handles.

The exception to the above is query tools that are specific to querying the database. Since those rely on state (e.g., receiving events) they need to live with `flux_mcp_server`.

## Components

Here is the architectural diagram and a breakdown of how the modules interact.

### Architecture

```console
                                         FLUX MCP SERVER (localhost:8089)
     (test_submit.py)                    (flux-mcp-server <options> <args>)
   +-----------------------+              +-------------------------------------+
   |                       |              |                                     |
   |  1. Connect Client    |              |  [API Framework]                    |
   |     Client(...)       |=============>|  FastAPI / FastMCP                  |
   |                       |   HTTP/SSE   |                                     |
   |                       |              |                                     |
   |  2. Call Tool         |              |  [Execution of flux-mcp function]   |
   |     flux_submit_job   |=============>|  flux_mcp.submit_job()              |
   |                       |              |          |                          |
   |                       |              |          v  [Flux Python SDK]       |
   |                       |              |      flux.job.submit()              |
   +-----------------------+              +----------+--------------------------+
               :                                     |
               :                                     | 3. Submit to Flux
               :                                     v
   +-----------:-----------+              +-------------------------------------+
   |  Database for Agents  |              |           Flux Instance             |
   |  (flux-mcp-state.db)  |              |       (flux-core, flux-sched)  💙   |
   |                       |              +----------+--------------------------+
   |  [Events Table]       |                         |
   |  - submit             |                         | 4. Generates Events
   |  - start              |<-------+                |    (submit, start, clean)
   |  - clean              |        |                v
   +-----------^-----------+        |     +-------------------------------------+
               :                    |     |  [Streaming Events Consumer]        |
               :                    |     |                                     |
               :                    +-----|  Events Engine (Background Thread)  |
               : 6. Verify                |  - flux.job.JournalConsumer         |
               :    (Poll DB)             |  - Normalizes Data                  |
               :                          |  - Writes to DB                     |
               :                          |                                     |
   +--------------------------------+     +-------------------------------------+
   |                                |
   |  7. Houston we have events!    |
   |     "Found events!"            |
   |                                |
   +--------------------------------+
```

#### Cluster handles

* manages connects to compute resources via a common interface
* base case is a local URI, but this will need to be extended to support more remote connects (beyond `ssh://`)
* registry can handle more than one, if delegation is eventually needed

```console
├── clusters
│   ├── __init__.py
│   ├── interface.py
│   ├── local.py
│   └── registry.py
```

#### Database interface

* database interface using sqlalchemy that supports sqlite, MySQL, Postgres, etc.
* is expecting to be created / called by MCP tools to write events to.
* agents / people can query them later!

```console
├── db
│   ├── __init__.py
│   ├── interface.py
│   ├── models.py
│   ├── __pycache__
│   │   ├── __init__.cpython-312.pyc
│   │   ├── interface.cpython-312.pyc
│   │   ├── models.cpython-312.pyc
│   │   └── views.cpython-312.pyc
│   └── views.py
```

#### Local (or standalone) event consumer

* Deploy alongside or standalone to watch events for a Flux URI
* Watch and connect to database to write events.

```console
├── events
│   ├── engine.py
│   ├── __init__.py
│   ├── __main__.py
│   └── receiver.py
```

#### Registry

* Functions from `flux-mcp` that should be exposed.

```console
├── registry.py
```

#### Main FastMCP server and app setup

* startup and shutdown - JournalConsumer needs tweaking so does not block (and prevent clean exit)
* starts / inits database, selecting backend from command line and/or environment.
* has middleware defined for auth (will be further worked on after discussion)

```console
├── server
│   ├── app.py
│   ├── __main__.py
│   ├── middleware
│   │   ├── __init__.py
│   │   └── token_auth.py
│   └── __pycache__
│       ├── app.cpython-312.pyc
│       └── __main__.cpython-312.pyc
```

#### MCP tools relevant to database

* most flux mcp tools are in `flux-mcp`
* these are specifically for writing / query of events/jobs in the database.
* we will need to hide these from normal agents so they do not hallucinate events!

```console
├── tools
│   ├── event.py
│   ├── __init__.py
│   └── query.py
└── version.py
```

## Thinking

### Events

I think we want to have an event stream (listener) instead of callback. The reason is because we are going to get much better granularity of events, and not rely upon the job state. I think we also would be able to retrieve older events (back up to some point) if needed, which would not be possible with a callback. If you miss a callback, you miss it. Finally, we can create different event streams (from even different components in Flux) to subscribe to as needed. I think this is a better design.

This introduces the question of where we are listening. If the service is running alongside some number of clusters, and we assume that we have active handles (or connections) to those clusters, we have two possible designs:

```console
# Option 1: direct handle
[flux-mcp-server]
    [flux.Flux() handle]

# Option 2: indirect handle
[flux-mcp-server] <-- [rpc/http] <-- [flux.Flux() handle]
```

Actually, for both cases, we would have an event service listening, and writing to the database via a function. The important part here is that we don't have _another_ kind of agent discover the endpoint and make faux events.

```console
# Option 3: Support direct or indirect handle via event scribe
[flux-mcp-server] <-- [mcp] <-- [scribe]
```

Importantly, we have:

- **State Decoupling:** the agent submits a job (via `clusters`) but checks its status via `db`. This means the Flux scheduler can restart, or the Agent can disconnect, and the memory / state is consistent.
- **Programmatic:** Everything is an API. Even the internal event logger acts like an agent, using MCP tools to report status updates to the database.
- **Plugin Backends:** The infrastructure supports swapping databases, auth schemes, and handle structures. This will work on-premises or in Kubernetes and beyond!

### Client

The above thinking had me design a client "cli" module that can be run standalone, or alongside (internal to) the server, primarily for simple, local, or testing cases.
The goal is that whether we are running this locally or externally, we use the same code paths.
Note that the event writer can be running via the same process as the server (embedded) or in the case of different clusters at a center, from different places.
