import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "AnimeList_v4.exe"
DATE = ROOT / "date"
STAGE_NAME = "AnimeList_v4.4-full-win64"
STAGE = ROOT / "dist" / STAGE_NAME
ZIP_PATH = ROOT / "dist" / (STAGE_NAME + ".zip")
DOCS = ["README.md", "LICENSE"]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def main():
    if not EXE.exists():
        raise SystemExit("AnimeList_v4.exe not found. Run tools/build.ps1 first.")

    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "date").mkdir(parents=True)

    shutil.copy2(EXE, STAGE / "AnimeList_v4.exe")
    for name in DOCS:
        shutil.copy2(ROOT / name, STAGE / name)

    for name in ("detail_main.json", "detail_extra.json"):
        shutil.copy2(DATE / name, STAGE / "date" / name)

    local = load_json(DATE / "local_data.json")
    local["plan"] = []
    local["broadcast"] = [x for x in (local.get("broadcast") or []) if not x.get("is_manual")]
    save_json(STAGE / "date" / "local_data.json", local)

    state = load_json(DATE / "app_state.json")
    clean_state = {}
    for key in ("ui_settings", "tip_mode", "broadcast_last_update",
                "progress", "archive_version"):
        if key in state:
            clean_state[key] = state[key]
    save_json(STAGE / "date" / "app_state.json", clean_state)

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in STAGE.rglob("*"):
            if path.is_file():
                z.write(path, path.relative_to(STAGE.parent).as_posix())

    # Verification
    prefix = STAGE_NAME + "/"
    with zipfile.ZipFile(ZIP_PATH) as z:
        with z.open(prefix + "date/local_data.json") as f:
            packaged_local = json.loads(f.read().decode("utf-8"))
        with z.open(prefix + "date/app_state.json") as f:
            packaged_state = json.loads(f.read().decode("utf-8"))
        names = z.namelist()
    assert packaged_local.get("plan") == []
    assert all(not x.get("is_manual") for x in packaged_local.get("broadcast") or [])
    assert "last_username" not in packaged_state
    assert not any(n.endswith("user_data.json") for n in names)
    assert not any("crimsonaries" in n.lower() for n in names)

    print("Package:", ZIP_PATH)
    print("Size MB:", round(ZIP_PATH.stat().st_size / 1024 / 1024, 2))
    print("Entries:")
    for name in names:
        print(" ", name)


if __name__ == "__main__":
    main()
