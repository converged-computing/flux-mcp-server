# Design

flux-mcp-server has an interesting design pattern because normally MCP functions are stateless, but when we
introduce a Flux handle (or events listener) it becomes stateful. Here is how I am thinking about
that separation:

- **flux_mcp**: provides the functions (tools) and is stateless. It wraps the Flux API and any function can accept a handle abstraction. It doesn't care about state and does not depend on it.
- **flux_mcp_server**: is the application. It has state, configuration, and databsae definitions. E.g., the server can receive updates in the form of events and write to a databsae for agents to access. It uses functions from `flux_mcp` and provides handles.

The exception to the above is query tools that are specific to querying the database. Since those rely on state (e.g., receiving events) they need to live with `flux_mcp_server`.

## Events

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

### Client

The above thinking had me design a client "cli" module that can be run standalone, or alongside (internal to) the server, primarily for simple, local, or testing cases.
The goal is that whether we are running this locally or externally, we use the same code paths.

Note that the scribe can be running via the same process as the server (embedded) or in the case of different clusters at a center, from different places.

TODO:

- need to write 
- Decide how connection to clusters should be. Persistent (e.g., event stream) vs. one off (e.g., create connection each time, stateless)

