import os
import re
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict, Counter
from rapidfuzz.distance import DamerauLevenshtein

MANUAL_NORMALIZATION = {
    "amanita_battarrae": "amanita_battarae",
    "agaricus_silvicola": "agaricus_sylvicola",
    "agaricus_silvaticus": "agaricus_sylvaticus",
    "pleurotus_eryngi": "pleurotus_eryngii",
    "pleurotus_djamor": "pleurotus_djamour",
    "panellus_stipticus": "panellus_stypticus",
    "ceratiomyxa_fructiculosa": "ceratiomyxa_fruticulosa",
    "lactarius_indigoo": "lactarius_indigo",
    "mycena_aciculata": "mycena_acicula",
    "agaricus_moelleri": "agaricus_moellerii",
    "cortinarius_casimirii": "cortinarius_casimiri",
    "amylocystis_lapponicus": "amylocystis_lapponica",
    "boletus_betulicola": "boletus_betulicolus",
    "entoloma_chalybaeum": "entoloma_chalybeum",
    "lactarius_omphaliiformis": "lactarius_omphaliformis",
    "cystostereum_murraii": "cystostereum_murrayi",
    "podofomes_trogiii": "podofomes_trogii",
    "cortinarius_variicolor": "cortinarius_variecolor",
    "trichaptum_fuscoviolaceum": "trichaptum_fuscovilaceum",
    "choiromyces_meandriformis": "choiromyces_maeandriformis",
    "daedaleopsis_confragosa": "daedalopsis_confragosa",
    "athallia_holocarpa": "athalia_holocarpa",
    "athallia_pyracea": "athalia_pyracea",
}

SAFE_MATCHES = {
    "tricholoma_imbricatum": "tricholoma_imbricatus",
    "leccinum_vulpinum": "leccinium_vulpinum",
    "cortinarius_helveolus": "cortinarius_helvolus",
    "sarcodon_squamosus": "sarcodon_squamatus",
    "lenzites_betulinus": "lenzites_betulina",
    "lecanora_umbrosa": "lecanora_umbrina",
    "parasola_conopilus": "parasola_conopilea",
    "marasmius_wynnei": "marasmius_wynneae",
}

BLOCKED_MATCHES = {
    frozenset({"cantharellus_cinereus", "cantharellus_cineteus"}),
    frozenset({"entoloma_scabrosum", "entoloma_scabiosum"}),
    frozenset({"melanohalea_exasperata", "melanohalea_exasperatula"}),
    frozenset({"entoloma_sericeum", "entoloma_sericellum"}),
    frozenset({"mycena_clavicularis", "mycena_clavularis"}),
    frozenset({"mycena_capillaripes", "mycena_capillaris"}),
    frozenset({"entoloma_sericeum", "entoloma_sericatum"}),
    frozenset({"russula_aurora", "russula_aurea"}),
}


def normalize_latin_name(name: str) -> str:
    name = re.sub(r"^[^a-zA-Z]+", "", name)
    name = re.sub(r"[^a-zA-Z\s]", " ", name)
    name = "_".join(name.lower().split()[:2])

    name = MANUAL_NORMALIZATION.get(name, name)
    return SAFE_MATCHES.get(name, name)


def get_latin_name_from_file(path: Path) -> str:
    try:
        content = path.read_text("utf-8")
        match = re.search(r"^latin_name:\s*(.*)$", content, re.MULTILINE)
        return normalize_latin_name(match.group(1)) if match else ""
    except Exception:
        return ""


def is_typo(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False

    dist = DamerauLevenshtein.distance(a, b)
    prefix_len = len(os.path.commonprefix([a, b]))
    return dist <= 2 and prefix_len >= 3


def are_similar(a: str, b: str) -> bool:
    if a == b:
        return True
    if frozenset((a, b)) in BLOCKED_MATCHES:
        return False

    a_parts, b_parts = a.split("_"), b.split("_")
    if len(a_parts) != 2 or len(b_parts) != 2:
        return False

    gen_dist = DamerauLevenshtein.distance(a_parts[0], b_parts[0])
    return gen_dist <= 1 and is_typo(a_parts[1], b_parts[1])


def find_canonical_name(name: str, existing_names: list[str]) -> str:
    if name in existing_names:
        return name

    # Sprawdzenie zamienionej kolejności (species_genus)
    parts = name.split("_")
    if len(parts) == 2:
        swapped = f"{parts[1]}_{parts[0]}"
        for existing in existing_names:
            if are_similar(swapped, existing):
                print(f"Matched (swap): {name} -> {existing}")
                return existing

    # Fuzzy match
    best_key, min_dist = name, float("inf")
    for existing in existing_names:
        if are_similar(name, existing):
            parts_a, parts_b = name.split("_"), existing.split("_")
            dist = DamerauLevenshtein.distance(
                parts_a[0], parts_b[0]
            ) + DamerauLevenshtein.distance(parts_a[1], parts_b[1])

            if dist < min_dist:
                min_dist = dist
                best_key = existing

    if best_key != name:
        print(f"Matched (fuzzy): {name} -> {best_key}")

    return best_key


def merge_mushroom_data(sources: list[Path], output_dir: str):
    articles = defaultdict(list)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    for source in sources:
        for file_path in source.glob("*"):
            if not file_path.is_file():
                continue

            latin_name = get_latin_name_from_file(file_path)
            if not latin_name:
                continue

            canonical = find_canonical_name(latin_name, list(articles.keys()))
            articles[canonical].append(file_path)

    processed_count = 0
    source_counts = []

    for name, files in articles.items():
        combined_text = "\n\n".join(f.read_text("utf-8") for f in files)

        if len(combined_text) <= 700:
            continue

        header = f"#{name}\n#no_sources: {len(files)}\n\n"
        (out_path / f"{name}.md").write_text(header + combined_text, "utf-8")

        source_counts.append(len(files))
        processed_count += 1
        if len(files) > 3:
            print(f"Rich entry: {name} ({len(files)} sources)")

    print(f"\nMerging complete. Total articles created: {processed_count}")
    generate_plots(sources, source_counts)


def generate_plots(sources, source_counts):
    data_dist = Counter(source_counts).most_common(10)
    _, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    ax1.bar([str(x[0]) for x in data_dist], [x[1] for x in data_dist], color="skyblue")
    ax1.set_title("Distribution of sources per article")
    ax1.set_xlabel("Number of sources")
    ax1.set_ylabel("Articles")

    source_names = [s.parent.name if s.name == "data" else s.name for s in sources]
    source_sizes = [len(list(s.glob("*"))) for s in sources]
    ax2.bar(source_names, source_sizes, color="salmon")
    ax2.set_title("Input files per source")
    ax2.set_ylabel("Files")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    INPUT_SOURCES = [
        Path("./ekologiapl/mushroom_data"),
        Path("./grzybypl/data"),
        Path("./nagrzybypl/atlas_grzybow"),
        Path("./wikipedia/grzyby"),
    ]
    merge_mushroom_data(INPUT_SOURCES, "./data")
