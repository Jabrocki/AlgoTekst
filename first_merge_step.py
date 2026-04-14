import os
from pathlib import Path
from collections import defaultdict, Counter
import re
import matplotlib.pyplot as plt


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
    no_sources = []
    for key, value in articles.items():
        texts = [Path(val).read_text(encoding="utf-8") for val in value]
        texts = "\n\n".join(texts)
        if len(texts) <= 600:
            continue
        header = f"#{key} \n#no_sources: {len(value)}\n\n"
        output = Path(os.path.join(out_dir, f"{key}.md"))
        no_sources.append(len(value))
        if len(value) > 3:
            print(f"{key} has {len(value)} sources")
        output.write_text(header + texts, encoding="utf-8")
    data_to_plot = Counter(no_sources).most_common(10)
    _, axs = plt.subplots(2, 1, figsize=(10, 8))
    axs[0].bar([str(x[0]) for x in data_to_plot], [x[1] for x in data_to_plot])
    axs[0].set_xlabel("Number of sources")
    axs[0].set_ylabel("Number of articles")
    axs[0].set_title("Distribution of number of sources per article")
    axs[1].bar(
        [str(source) for source in file_sources],
        [len(list(source.glob("*"))) for source in file_sources],
    )
    axs[1].set_xlabel("Source")
    axs[1].set_ylabel("Number of articles")
    axs[1].set_title("Number of articles per source")

    plt.show()


merger(
    [
        Path("./ekologiapl/mushroom_data"),
        Path("./grzybypl/data"),
        Path("./nagrzybypl/atlas_grzybow"),
    ],
    "./data",
)
