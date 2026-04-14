from pathlib import Path

folder = Path("./atlas_grzybow")

for path in folder.glob("*"):
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        text = text.replace("name:", "latin_name:", 1)
        path.write_text(text, encoding="utf-8")
