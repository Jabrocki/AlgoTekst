import os
from pathlib import Path
from collections import defaultdict
import re


def get_latin_name(path: Path) -> str:
    latin_name = ""
    for line in path.read_text("utf-8").splitlines():
        if line.startswith("latin_name:"):
            latin_name = line.removeprefix("latin_name:").strip()
            break

    latin_name = re.sub(r"^[^a-zA-Z]+", "", latin_name)
    latin_name = " ".join(latin_name.split()[:2])

    return latin_name.replace(" ", "_").lower()


def merger(file_sources: list[Path], out_dir: str):
    articles = defaultdict(list)

    for source in file_sources:
        for path in source.glob("*"):
            if not path.is_file():
                continue

            latin_name = get_latin_name(path)
            articles[latin_name].append(str(path))

    os.makedirs(out_dir, exist_ok=True)
    for key, value in articles.items():
        texts = [Path(val).read_text(encoding="utf-8") for val in value]
        texts = "\n\n".join(texts)
        header = f"#{key} \n#no_sources: {len(value)}\n\n"
        output = Path(os.path.join(out_dir, f"{key}.md"))
        output.write_text(header + texts, encoding="utf-8")


merger(
    [
        Path("./ekologiapl/mushroom_data"),
        Path("./grzybypl/data"),
        Path("./nagrzybypl/atlas_grzybow"),
    ],
    "./data",
)
