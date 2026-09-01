# SCI Conformance

A runtime is **SCI-conformant** when it satisfies the normative clauses of the specs it claims. The
checklist below maps each clause to a verifiable behavior. The checks are **executable**: the
contract test suite in
[`sheeternetes-onprem/tests`](https://github.com/sncfoundation/sheeternetes-onprem/tree/main/tests)
exercises them against a reference apiserver and doubles as the conformance harness — point it at
your apiserver to self-certify.

## SCRI Core

| # | Clause | Check |
|---|--------|-------|
| C1 | §3 | The workbook exposes Deployments, Nodes, and Pods tabs with the normative columns. |
| C2 | §4 | A request with a missing/wrong token is rejected with `401`. |
| C3 | §5 | `GET ?kind=pods\|nodes\|deployments` returns `{items:[…]}`; an unknown kind returns `400`. |
| C4 | §6 | A heartbeat upserts the Node and returns this node's desired pods. |
| C5 | §6 | Pods assigned to the node are returned `desired:"Running"` with image/command/reqs. |
| C6 | §6 | A reported pod no longer assigned to the node is returned `desired:"Terminating"`. |
| C7 | §6 | A Node silent beyond the TTL becomes `NotReady` and its pods reschedule (failover). |
| C8 | §7 | Exactly `replicas` pods per Deployment, named `<deployment>-<ordinal>` from 1. |
| C9 | §9 | `apply`, `scale`, `delete` behave as specified; an unknown action returns `400`. |

## SCRI Full (Core plus)

| # | Clause | Check |
|---|--------|-------|
| F1 | §7 | Placement respects `cpu_req`/`mem_req`; a pod that fits nowhere is `Unschedulable`. |
| F2 | §7 | Placement is sticky across rounds when the node stays eligible. |
| F3 | §7/§9 | `cordon` stops new placements but keeps existing pods; `drain` evicts them. |
| F4 | §7 | `node_selector` is honored against Node `labels`. |
| F5 | §7 | `NoSchedule` taints repel pods that lack a matching toleration. |
| F6 | §9 | HMAC-signed POSTs are accepted; unsigned, tampered, or stale ones are rejected. |
| F7 | §3 | The Events tab is present and populated. |

## Self-certifying

```bash
git clone https://github.com/sncfoundation/sheeternetes-onprem
cd sheeternetes-onprem && pip install openpyxl pytest && python -m pytest -q
```

The reference apiserver passes all of the above. To certify a *different* runtime, run the same
suite against it (adapt the fixtures to your transport) and confirm each check.

## Getting listed

Passing runtimes and distributions may apply to the SNCF
[conformance program](https://github.com/sncfoundation/governance/issues/2): open an issue there
with your runtime, the level claimed (Core or Full), and evidence (the suite output). On review you
are added to the public listing and may use the "Certified Sheet-Native" mark per the
[Distribution Program](https://github.com/sncfoundation/governance/issues/3).
