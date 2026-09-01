<div align="center">

<img src="https://sncfoundation.github.io/logos/sncf-512.png" width="110" alt="SCI">

# Sheet Container Initiative (SCI)

**Open specifications for sheet-native container runtimes.**

The [OCI](https://opencontainers.org) gave the cloud-native world a common image, runtime, and
distribution format. The SCI does the same for the substrate humanity actually trusts — the
spreadsheet. A SCI-conformant runtime schedules and runs containers with a spreadsheet as its
control plane, and can be certified against these specs.

A [Sheet-Native Computing Foundation](https://sncfoundation.github.io) initiative.

</div>

---

## Why a standard?

Two independent runtimes already speak the same contract — the Apps Script apiserver in
[`sheeternetes`](https://github.com/sncfoundation/sheeternetes) (Google Sheets) and the Python
apiserver in [`sheeternetes-onprem`](https://github.com/sncfoundation/sheeternetes-onprem)
(Excel/LibreOffice). Where there are two implementations, there should be a spec. The SCI
**writes down what already runs** so that:

- anyone can build a conforming runtime (a new kubelet, a new backend) and have it interoperate;
- distributions and products can be **certified** (see the [conformance program](https://github.com/sncfoundation/governance/issues/2));
- the whole thing is teachable — it is, unavoidably, a working tutorial on what OCI and CRI really are.

## The specifications

The SCI is three specs, mirroring the OCI's split. Each is versioned independently and codifies
current, shipping behavior — new behavior lands in a spec's roadmap first, then in normative text
only once it ships in a reference implementation.

| Spec | Mirrors | Defines | Status |
|------|---------|---------|--------|
| [**SCRI**](specs/scri-v0.1.md) — Sheet Container Runtime Interface | CRI / runtime-spec | The apiserver ↔ node-agent contract: the store, reads, heartbeat, desired-state reconciliation, pod lifecycle, control verbs, auth. | **v0.1 (experimental)** |
| **SICF** — Sheet-Native Image Container Format | OCI image-spec | What a sheet-native image is: layers as tabs, a manifest row, base64 blobs, content digests. | drafting ([#47](https://github.com/sncfoundation/sheeternetes/issues/47)) |
| **SDS** — Sheet Distribution Spec | OCI distribution-spec | How images move between sheets and registries: the pull/push protocol, registry-in-cells. | planned |

## Reference implementations

| Runtime | Substrate | SCRI |
|---------|-----------|------|
| [sheeternetes](https://github.com/sncfoundation/sheeternetes) | Google Sheets (Apps Script) | v0.1 |
| [sheeternetes-onprem](https://github.com/sncfoundation/sheeternetes-onprem) | Excel / LibreOffice (Python) | v0.1 |

## Conformance

A runtime is SCI-conformant if it passes the checks in [CONFORMANCE.md](CONFORMANCE.md), which map
one-to-one to the normative MUST clauses of each spec. The checks are executable — the contract
test suite in `sheeternetes-onprem/tests` doubles as the conformance harness. Passing runtimes may
apply to be listed via the [conformance program](https://github.com/sncfoundation/governance/issues/2).

## Governance

The SCI is a working group under the SNCF. Specs change by pull request; a normative change
(anything a conformant runtime must obey) requires a version bump and two implementers' review.
Discussion happens in issues on this repo.

---

<sub>Apache-2.0. Yes, it is a real specification. No, you should not run production on it. It reconciles. 💩</sub>
