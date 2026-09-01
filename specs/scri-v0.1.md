# SCRI — Sheet Container Runtime Interface

**Version:** 0.1 · **Status:** Experimental · **Part of:** [Sheet Container Initiative](../README.md)

SCRI defines the contract between a **control plane** (an *apiserver* backed by a spreadsheet) and
a **node agent** (a *kubelet*) that runs containers on a host. A runtime that implements this
contract can be driven by any SCRI-conformant client (`skctl`, a bridge, another kubelet) and can
be certified for conformance.

This version codifies the behavior shipping in the reference implementations
([`sheeternetes`](https://github.com/sncfoundation/sheeternetes),
[`sheeternetes-onprem`](https://github.com/sncfoundation/sheeternetes-onprem)). It is intentionally
descriptive, not aspirational.

## 1. Conventions

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be interpreted
as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

## 2. Terminology

- **Workbook** — the spreadsheet that is the durable store and single source of truth.
- **apiserver** — the process serving the SCRI transport over a workbook. It is also the scheduler.
- **node agent** (kubelet) — a process on a host that reports the host as a **Node** and converges
  local container state to the desired set the apiserver returns.
- **Deployment** — desired workload: an image and a replica count. **Pod** — one running replica.
- **control plane state** — the four tabs defined in §3.

## 3. The store

The workbook **MUST** contain four tabs. Row 1 of each is the header; each subsequent non-empty
row is a record. An apiserver **MAY** add trailing columns; clients **MUST** ignore columns they do
not recognize. The normative columns are:

| Tab | Columns |
|-----|---------|
| **Deployments** | `name`, `image`, `replicas`, `cpu_req`, `mem_req`, `command`, `node_selector`, `tolerations` |
| **Nodes** | `name`, `ip`, `cpu_total`, `cpu_used`, `mem_total`, `status`, `last_heartbeat`, `schedulable`, `labels`, `taints` |
| **Pods** | `name`, `deployment`, `node`, `phase`, `container_id` |
| **Events** | `ts`, `kind`, `object`, `message` |

`cpu_*` are integer **millicores**; `mem_*` are integer **MiB**. `node_selector`/`labels` are
`k=v` pairs joined by commas; `tolerations` is a comma list of `k=v` or bare `k`; `taints` is a
comma list of `k=v:Effect`. A Deployment's `name` **MUST** be unique.

## 4. Transport and authentication

SCRI is served over HTTP. Reads use `GET`; mutations and heartbeats use `POST` with a JSON body.

Every request **MUST** carry a shared **token** (query parameter `token` on `GET`, field `token`
in the body on `POST`). A request with a missing or wrong token **MUST** be rejected with `401`.

An apiserver **MAY** additionally require **HMAC signing** of `POST` requests (see §9). If it does,
unsigned or invalid requests **MUST** be rejected with `401`.

## 5. Read interface

```
GET /?token=<t>&kind=<pods|nodes|deployments|events>   ->   {"items": [ {...}, ... ]}
```

The apiserver **MUST** return the records of the named tab as an array of objects keyed by header.
An unknown `kind` **MUST** return `400`.

## 6. Node lifecycle and heartbeat

A node agent **MUST** periodically `POST` a heartbeat:

```json
{ "token": "<t>", "node": "<name>", "ip": "<ip>",
  "cpu_total": 4000, "mem_total": 8192,
  "pods": [ { "name": "web-1", "phase": "Running", "container_id": "…" } ] }
```

On receipt the apiserver **MUST**:

1. upsert the Node, set its `last_heartbeat` to now and treat it as **Ready**;
2. run scheduling (§7) across all Deployments and Nodes;
3. persist the resulting Pods; and
4. respond with **this node's desired pod set**:

```json
{ "pods": [
  { "name": "web-1", "desired": "Running", "image": "nginx",
    "command": "", "cpu_req": 100, "mem_req": 64, "deployment": "web" },
  { "name": "old-2", "desired": "Terminating" }
] }
```

For each pod the apiserver has assigned to the requesting node it **MUST** return an entry with
`desired: "Running"` and the fields needed to start it. For each pod the node **reported** running
that is no longer assigned to it, the apiserver **MUST** return `desired: "Terminating"`. The node
agent **MUST** start `Running` pods it is not already running and stop `Terminating` pods.

A Node whose `last_heartbeat` is older than the **node TTL** (default 30s) **MUST** be treated as
`NotReady` and **MUST NOT** receive new placements; pods assigned to it **MUST** be rescheduled onto
Ready nodes (failover).

## 7. Scheduling and desired state

Given the Deployments and the Ready Nodes, the apiserver computes the desired Pods.

- It **MUST** create exactly `replicas` pods per Deployment, named `<deployment>-<ordinal>` with
  `ordinal` starting at 1.
- It **MUST** assign each pod to at most one Node and reflect that in the Pods tab.
- It **SHOULD** keep a pod on its current Node across scheduling rounds (sticky placement) when that
  Node remains eligible.
- It **SHOULD** be resource-aware: respect `cpu_req`/`mem_req` against a Node's `cpu_total`/
  `mem_total`, and mark a pod that fits nowhere with phase `Unschedulable` and an empty `node`.
- It **SHOULD** honor **cordon**: a Node with `schedulable = FALSE` receives no new pods but keeps
  the pods it already runs.
- It **MAY** honor node **affinity** (`node_selector` ⊆ Node `labels`) and **taints/tolerations**
  (a pod is placed on a `NoSchedule`-tainted Node only if it tolerates every such taint).
- It **SHOULD** write `cpu_used` per Node to reflect placed allocation, and Node `status` to one of
  `Ready`, `NotReady`, `SchedulingDisabled`.

## 8. Pod lifecycle

A Pod's `phase` **MUST** be one of: `Pending` (assigned, not yet reported running), `Running`
(reported by its Node), `Terminating` (marked for stop), `Unschedulable` (no eligible Node).

## 9. Control verbs

Mutations are `POST` with an `action` field. An apiserver **MUST** implement the **Core** verbs and
**SHOULD** implement the rest; unknown actions **MUST** return `400`.

| Action | Level | Body | Effect |
|--------|-------|------|--------|
| `apply` | MUST | `{deployments:[…]}` | create/update Deployments |
| `scale` | MUST | `{name, replicas}` | set a Deployment's replica count |
| `delete` | MUST | `{name}` | remove a Deployment |
| `cordon` / `uncordon` | SHOULD | `{name}` | set a Node's `schedulable` |
| `drain` | SHOULD | `{name}` | cordon a Node and evict its pods |
| `migrate` | MAY | `{name, node}` | pin a pod to a target Node |
| `label` / `taint` | MAY | `{name, spec}` | edit a Node's labels/taints |

### HMAC signing (optional, normative if implemented)

If an apiserver requires signing, a signed `POST` **MUST** carry:

- `X-SNCF-Timestamp`: the Unix time of signing, as a string;
- `X-SNCF-Signature`: the lowercase hex of `HMAC-SHA256(key, "<timestamp>.<raw-body-bytes>")`.

The apiserver **MUST** reject the request if the timestamp skew exceeds the signing TTL (default
300s), and **MUST** compare signatures in constant time.

## 10. Conformance levels

- **SCRI Core** — §3 store (Deployments, Nodes, Pods), §5 reads, §6 heartbeat with
  Running/Terminating semantics and TTL failover, §9 Core verbs, §4 token auth.
- **SCRI Full** — Core plus resource-aware scheduling, sticky placement, cordon/drain, affinity,
  taints/tolerations, the Events tab, and HMAC signing.

See [CONFORMANCE.md](../CONFORMANCE.md) for the executable checklist.

## 11. Roadmap (non-normative)

Multi-peer federation, a rendezvous "Mesh" descriptor, pod topology spread, and image references
(once [SICF](https://github.com/sncfoundation/sheeternetes/issues/47) lands) are candidates for
future versions. They become normative only after shipping in a reference implementation.
