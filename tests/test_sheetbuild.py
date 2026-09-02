"""Tests for the SICF reference tool (tools/sheetbuild.py). No Docker required:
we synthesize `docker save`-shaped tars, pack them into a spreadsheet store, unpack,
and assert byte-exact round-trips + digest verification + cell sharding."""
import os, sys, io, json, tarfile, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import pytest
import sheetbuild as sb


def make_save_tar(path, layers, config=b'{"architecture":"amd64","os":"linux"}', tags=("test:latest",)):
    """Write a minimal `docker save`-format tar: manifest.json + config + layer tars."""
    with tarfile.open(path, "w") as t:
        def add(name, data):
            ti = tarfile.TarInfo(name); ti.size = len(data); t.addfile(ti, io.BytesIO(data))
        add("config.json", config)
        lpaths = []
        for i, blob in enumerate(layers):
            p = f"layer{i}/layer.tar"; add(p, blob); lpaths.append(p)
        add("manifest.json", json.dumps([{"Config": "config.json",
                                           "RepoTags": list(tags), "Layers": lpaths}]).encode())

def layers_from_tar(path):
    """Return the layer blobs (in manifest order) from a docker-load tar."""
    with tarfile.open(path, "r") as t:
        manifest = json.load(t.extractfile("manifest.json"))[0]
        return [t.extractfile(p).read() for p in manifest["Layers"]], \
               t.extractfile(manifest["Config"]).read()


def test_round_trip_single_layer(tmp_path):
    src, store, out = tmp_path / "img.tar", tmp_path / "s.xlsx", tmp_path / "out.tar"
    make_save_tar(src, [b"hello doom, this is a rootfs layer"])
    info = sb.import_image(str(src), "doom:shareware", str(store))
    assert info["layers"] == 1 and info["name"] == "doom:shareware"
    sb.export_image("doom:shareware", str(store), str(out))
    blobs, cfg = layers_from_tar(str(out))
    assert blobs == [b"hello doom, this is a rootfs layer"]      # byte-exact
    assert cfg == b'{"architecture":"amd64","os":"linux"}'

def test_multi_chunk_sharding(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "MAX_CELL", 100)                     # force many small cells
    big = os.urandom(4096)                                        # ~5500 base64 chars -> ~55 chunks
    src, store, out = tmp_path / "b.tar", tmp_path / "s.xlsx", tmp_path / "o.tar"
    make_save_tar(src, [big])
    sb.import_image(str(src), "big:1", str(store))
    wb = sb._open(str(store))
    digest = sb._sha256(big)
    chunks = [r for r in sb._rows(wb[sb.LAYERS]) if r["digest"] == digest]
    assert len(chunks) > 1                                        # actually sharded
    assert all(len(str(c["data"])) <= 100 for c in chunks)       # every cell within cap
    sb.export_image("big:1", str(store), str(out))
    assert layers_from_tar(str(out))[0] == [big]                 # reassembled byte-exact

def test_digest_mismatch_is_rejected(tmp_path):
    src, store, out = tmp_path / "i.tar", tmp_path / "s.xlsx", tmp_path / "o.tar"
    make_save_tar(src, [b"trust but verify"])
    sb.import_image(str(src), "x:1", str(store))
    # corrupt one chunk cell in the store
    import openpyxl
    wb = openpyxl.load_workbook(str(store)); ws = wb[sb.LAYERS]
    ws.cell(row=2, column=sb.LAYERS_COLS.index("data") + 1, value="Y29ycnVwdA==")
    wb.save(str(store))
    with pytest.raises(ValueError, match="digest mismatch"):
        sb.export_image("x:1", str(store), str(out))

def test_multi_layer_order_preserved(tmp_path):
    src, store, out = tmp_path / "m.tar", tmp_path / "s.xlsx", tmp_path / "o.tar"
    original = [b"base layer", b"middle layer", b"top layer"]
    make_save_tar(src, original)
    info = sb.import_image(str(src), "multi:1", str(store))
    assert info["layers"] == 3
    sb.export_image("multi:1", str(store), str(out))
    assert layers_from_tar(str(out))[0] == original             # order + bytes intact

def test_shared_layer_stored_once(tmp_path):
    # two images that share an identical layer -> chunks written once (content addressed)
    shared = b"a layer both images share"
    a, b, store = tmp_path / "a.tar", tmp_path / "b.tar", tmp_path / "s.xlsx"
    make_save_tar(a, [shared, b"only in a"])
    make_save_tar(b, [shared, b"only in b"])
    sb.import_image(str(a), "a:1", str(store))
    sb.import_image(str(b), "b:1", str(store))
    wb = sb._open(str(store))
    digest = sb._sha256(shared)
    shared_rows = [r for r in sb._rows(wb[sb.LAYERS]) if r["digest"] == digest]
    assert len(shared_rows) == 1                                 # deduped, not stored twice
    # and both images still export correctly
    for name, uniq in (("a:1", b"only in a"), ("b:1", b"only in b")):
        o = tmp_path / f"{name.replace(':','_')}.tar"
        sb.export_image(name, str(store), str(o))
        assert layers_from_tar(str(o))[0] == [shared, uniq]

def test_import_uses_repotag_when_name_omitted(tmp_path):
    src, store = tmp_path / "r.tar", tmp_path / "s.xlsx"
    make_save_tar(src, [b"x"], tags=("auto:tag",))
    info = sb.import_image(str(src), "", str(store))
    assert info["name"] == "auto:tag"
