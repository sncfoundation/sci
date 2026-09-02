# SICF reference tools

**`sheetbuild.py`** — pack an OCI image into a spreadsheet (the SICF native image store) and back.
Reference implementation of [SICF v0.1](../specs/sicf-v0.1.md). Requires `openpyxl`.

```bash
pip install openpyxl

# 1. produce an OCI image tar with Docker (on any Docker host)
docker save doom:shareware -o doom.tar

# 2. pack it INTO a spreadsheet — layers become base64 chunks in the Layers tab
python tools/sheetbuild.py import doom.tar --name doom:shareware --store cluster.xlsx
python tools/sheetbuild.py ls --store cluster.xlsx

# 3. unpack it back to a docker-loadable tar (every layer's sha256 is verified)
python tools/sheetbuild.py export doom:shareware --store cluster.xlsx --out out.tar
docker load < out.tar
```

The store workbook holds the image per the spec: an `Images` tab (name, digest, config,
layers, created, size) and a `Layers` tab (digest, ordinal, media_type, data). Layers are
content-addressed by sha256, sharded to respect the cell-character limit (Excel 32,767 /
Sheets 50,000; capped conservatively at 30,000, override with `SICF_MAX_CELL`).

## DOOM as a SICF image (the demo)

DOOM is small enough to live entirely in a spreadsheet: shareware `DOOM1.WAD` (~4 MB) plus a
minimal engine is a few hundred cells — far under the 10M-cell workbook limit. Package it once
with `sheetbuild import`, and a SICF-aware kubelet resolves `image: sicf:doom:shareware` by
`export`-ing from the sheet and `docker load`-ing it. **Execution stays on the node** — the
spreadsheet only stores the image and schedules the pod. Tracked in
[sci#6](https://github.com/sncfoundation/sci/issues/6); the runtime side (kubelet `sicf:`
resolution) lands in `sheeternetes-onprem` next.
