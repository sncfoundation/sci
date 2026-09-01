# SICF — Sheet-Native Image Container Format

**Version:** 0.1 · **Status:** Experimental · **Part of:** [Sheet Container Initiative](../README.md)

SICF is the OCI image-spec analog for sheet-native runtimes. It defines two things:

1. how a container image can be referenced by an ordinary **OCI registry** (interop mode), and
2. how an image can be stored **natively inside a spreadsheet** — layers as tabs, blobs as base64
   in cells, addressed by content digest (native mode).

A SCRI runtime **SHOULD** support both. The point of SICF is that the two are interchangeable: a
bridge converts an OCI image into a SICF workbook and back, so a workload can run from a public
registry or from a fully self-contained, air-gapped spreadsheet with no external dependency.

## 1. Conventions

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, **MAY** follow
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119). A **digest** is `sha256:<hex>` over the named
bytes. **base64** means standard base64 without line breaks.

## 2. Image references

A Deployment's `image` field selects the mode:

- **OCI mode** — a normal reference such as `nginx:alpine` or `ghcr.io/org/app:1.2`. The node agent
  resolves and pulls it through the host container engine (e.g. `docker pull`). This is the default
  and requires nothing from SICF; it exists so sheet-native clusters interoperate with the entire
  container ecosystem out of the box.
- **SICF native mode** — a reference of the form `sicf:<image-name>` (optionally
  `sicf:<workbook-id>/<image-name>`). The node agent resolves it from a SICF **image store** — a
  workbook laid out per §3 — with no external registry.

A runtime **MUST** support OCI mode and **SHOULD** support SICF native mode.

## 3. Native layout (the image store)

A SICF image store is a workbook with two tabs.

### Images

One row per image manifest.

| Column | Meaning |
|--------|---------|
| `name` | image name, e.g. `web:v1` (**MUST** be unique in the store) |
| `digest` | `sha256:` of the config blob — the image's content identity |
| `config` | base64 of the OCI-style image config JSON (env, entrypoint, cmd, working_dir, user) |
| `layers` | ordered, comma-separated list of layer digests |
| `created` | RFC 3339 timestamp |
| `size` | total uncompressed size in bytes (informational) |

### Layers

One row per **chunk**. A layer whose base64 exceeds the cell limit (§5) **MUST** be split into
ordered chunks sharing one `digest`.

| Column | Meaning |
|--------|---------|
| `digest` | `sha256:` of the whole layer tar (same for every chunk of that layer) |
| `ordinal` | 0-based chunk index within the layer |
| `media_type` | e.g. `application/vnd.oci.image.layer.v1.tar+gzip` |
| `data` | base64 of this chunk's bytes |

### Resolving and running (the puller)

To run `sicf:web:v1`, a node agent **MUST**:

1. read the `Images` row for `web:v1`;
2. for each digest in `layers`, gather all `Layers` rows with that digest **ordered by `ordinal`**,
   base64-decode and concatenate their `data`, and **verify** the result hashes to the digest
   (a mismatch **MUST** abort the pull);
3. apply the layers in order to build a rootfs;
4. decode `config` and run the entrypoint/cmd with its env, honoring the Deployment's `command`
   override if present.

An integrity failure at any step **MUST** fail the pod (phase remains `Pending`/errored), and
**SHOULD** write an Event.

## 4. The OCI ⇆ SICF bridge

Interop is provided by a build tool (`sheetbuild`, reference name):

- `sheetbuild import <oci-ref>` — pull an OCI image, split each layer into cell-sized base64 chunks,
  and write the `Images`/`Layers` rows. The resulting store **MUST** reproduce the original layer
  digests, so an imported image is byte-identical to its OCI source.
- `sheetbuild export <name> <oci-ref>` — reassemble a SICF image and push it to an OCI registry.

Because both sides address content by the same `sha256:` digests, import→export is a round trip.

## 5. Target payloads and limits

SICF native mode is bounded by the spreadsheet backend. For Google Sheets: **50,000 characters per
cell** and **10,000,000 cells per workbook**. Therefore:

- a chunk's base64 **MUST NOT** exceed the cell character limit; implementations **SHOULD** cap a
  chunk at ~49,000 base64 chars (~36 KB of bytes) to stay clear of it;
- an image store **MUST** stay within the workbook cell limit; large images **SHOULD** use OCI mode
  instead.

Native mode is therefore intended for **small images**: static Go/Rust binaries, `scratch`- and
`alpine`-based images, and **WASM modules** (which pair naturally with
[SheetAssembly](https://github.com/sncfoundation/sheeternetes/issues/24)). A multi-gigabyte image
(e.g. a CUDA base) is out of scope for native mode and **SHOULD** be referenced via OCI mode. A
runtime **SHOULD** report an image that would exceed the backend limits rather than truncate it.

## 6. Conformance

- **SICF Interop** — the runtime resolves OCI-mode `image` references. (Every SCRI runtime that runs
  real containers already meets this.)
- **SICF Native** — the runtime resolves `sicf:` references from a §3 store, verifies layer digests,
  and runs the image. A conformant `sheetbuild` provides a lossless OCI import/export round trip.

See [CONFORMANCE.md](../CONFORMANCE.md).

## 7. Roadmap (non-normative)

Signed images (integrate with SheetSign), a shared cross-workbook layer cache addressed by digest,
and zstd chunking are candidates for later versions — normative only once shipped in a reference
implementation. Distribution of SICF stores between workbooks/registries is specified separately in
**SDS** (the Sheet Distribution Spec).
