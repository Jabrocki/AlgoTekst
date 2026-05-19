"""
RAG-chat o grzybach: retrieval z pgvector (Supabase) + generacja przez lokalną Gemmę (Ollama).

Uruchom:
    python rag_chat.py

Wymagania:
<<<<<<< HEAD
    1. Ollama uruchomiona w tle (https://ollama.com).
    2. Pobrany model:  ollama pull gemma3:4b
=======
    1. Ollama uruchomiona w tle (instalator z https://ollama.com).
    2. Pobranie modeli:  
       ollama pull gemma3:4b
       ollama pull nomic-embed-text
>>>>>>> 227926647e68554d02d59847857acef1fe841fdc
    3. pip install -r requirements.txt

Komendy w chacie:
    /metric <cosine|l1|l2|jaccard>   - zmiana metryki podobieństwa
    /topk <n>                        - ile dokumentów pobierać (1-15)
    /show                            - pokaż aktualne ustawienia
    /help                            - lista komend
    q | quit | exit | wyjscie        - zakończ
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from collections import defaultdict, OrderedDict
from typing import List, Tuple

import numpy as np
import psycopg2
import ollama
from sentence_transformers import SentenceTransformer

# --- Konfiguracja ---------------------------------------------------------
DB_URL = os.getenv(
    "MUSHROOM_DB_URL",
    "postgresql://postgres.vhwxrmwtekxelbarhcgl:grzyby12345!!!"
    "@aws-0-eu-west-1.pooler.supabase.com:6543/postgres",
)
<<<<<<< HEAD
EMBED_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
LLM_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

DEFAULT_METRIC = os.getenv("RAG_METRIC", "cosine").lower()
DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
FETCH_MULTIPLIER = 25          # ile chunków ściągnąć z DB żeby zgrupować po gatunku
MAX_CHUNKS_PER_SPECIES = 6     # max chunków sklejanych w jeden blok kontekstu
MAX_CTX_CHARS_PER_SPECIES = 3500
MAX_CTX_CHARS_TOTAL = 10000

VALID_METRICS = {"cosine", "l1", "l2", "jaccard"}

# Operatory pgvector (https://github.com/pgvector/pgvector#querying)
PGV_OP = {
    "cosine": "<=>",   # cosine distance
    "l2": "<->",       # euclidean distance
    "l1": "<+>",       # taxicab distance (pgvector >= 0.7)
}
=======
EMBED_MODEL_NAME = "nomic-embed-text"
LLM_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")  # zmień na gemma3:1b jeżeli mało RAM
TOP_K = 4               # ile fragmentów wciągamy do kontekstu
MAX_CTX_CHARS = 2500    # przycinanie pojedynczego opisu, by nie zalać promptu
>>>>>>> 227926647e68554d02d59847857acef1fe841fdc

SYSTEM_PROMPT = (
    "Jesteś polskim mykologiem. Odpowiadasz po polsku, krótko i konkretnie.\n"
    "Masz zawsze dany KONTEKST z fragmentami opisów grzybów oraz pole TEMAT "
    "wskazujące, którego gatunku dotyczy pytanie.\n"
    "Zasady:\n"
    "1. Odpowiadasz WYŁĄCZNIE o gatunku wskazanym w polu TEMAT (lub – jeśli TEMAT pusty – "
    "   o gatunku z pierwszego bloku [1] kontekstu).\n"
    "2. NIE opisuj innych gatunków, nawet jeśli pojawiają się w kontekście jako "
    "   'gatunki podobne' czy 'mylone z'. Możesz je co najwyżej krótko wymienić.\n"
    "3. Korzystaj tylko z faktów z kontekstu. Niczego nie wymyślaj.\n"
    "4. Używaj polskiej nazwy gatunku, a w nawiasie podaj łacińską.\n"
    "5. Przy gatunkach trujących wyraźnie to zaznacz.\n"
    "6. Na końcu dodaj linijkę: Źródła: [Polska nazwa (Łacińska nazwa)]."
)

<<<<<<< HEAD
POLISH_STOPWORDS = {
    "i", "oraz", "lub", "albo", "ale", "ze", "sie", "nie", "to", "ten", "ta", "te",
    "tam", "tu", "tak", "jak", "co", "czy", "jest", "sa", "byc", "byl", "byla",
    "bylo", "byly", "ma", "maja", "mial", "miala", "moze", "mozna", "trzeba",
    "tylko", "takze", "rowniez", "wiec", "gdy", "gdzie", "kiedy", "ktory",
    "ktora", "ktore", "ktorzy", "tym", "tych", "tej", "tymi", "na", "do",
    "we", "ze", "od", "po", "przy", "bez", "dla", "pod", "nad", "przed",
    "za", "przez", "wedlug", "the", "of", "and", "or", "for", "with",
}

# --- Embedder -------------------------------------------------------------
print(f"[init] Ładowanie embeddera ({EMBED_MODEL_NAME})...", file=sys.stderr)
embedder = SentenceTransformer(EMBED_MODEL_NAME)


# --- Pomocnicze ----------------------------------------------------------
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


_TOKEN_RE = re.compile(r"[A-Za-zĄąĆćĘęŁłŃńÓóŚśŹźŻż]{3,}")


def tokenize(text: str) -> set[str]:
    """Tokeny lower-case, bez polskich znaków, min. 3 znaki, bez stopwords."""
    out: set[str] = set()
    for tok in _TOKEN_RE.findall(text or ""):
        t = strip_accents(tok.lower())
        if t in POLISH_STOPWORDS or len(t) < 3:
            continue
        out.add(t)
    return out


def extract_polish_name(name_or_desc: str) -> str | None:
    # baza: name = "Polska nazwa (Latin Name)"
    if not name_or_desc:
        return None
    m = re.match(r"^\s*(.+?)\s*\(([^()]+)\)\s*$", name_or_desc)
    if m:
        return m.group(1).strip()
    # fallback: szukaj frontmatter (gdyby kiedyś doszedł)
    m = re.search(r"^polish_name:\s*(.+)$", name_or_desc, re.MULTILINE)
    return m.group(1).strip() if m else None


def extract_latin_name(name_or_desc: str) -> str | None:
    if not name_or_desc:
        return None
    m = re.match(r"^\s*(.+?)\s*\(([^()]+)\)\s*$", name_or_desc)
    if m:
        return m.group(2).strip()
    m = re.search(r"^latin_name:\s*(.+)$", name_or_desc, re.MULTILINE)
    return m.group(1).strip() if m else None


# --- Cache unikalnych gatunków (do dopasowania po nazwie) -----------------
_UNIQUE_NAMES_CACHE: list[str] | None = None


def load_unique_names() -> list[str]:
    """Lista unikalnych wartości kolumny `name` w bazie."""
    global _UNIQUE_NAMES_CACHE
    if _UNIQUE_NAMES_CACHE is None:
        with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
            cur.execute("SELECT DISTINCT name FROM mushrooms;")
            _UNIQUE_NAMES_CACHE = [r[0] for r in cur.fetchall() if r[0]]
    return _UNIQUE_NAMES_CACHE


# Cache pełnych chunków używany przez Jaccard (dużo danych – ładujemy leniwie)
_ALL_ROWS_CACHE: list[tuple[str, str]] | None = None


def load_all_rows() -> list[tuple[str, str]]:
    global _ALL_ROWS_CACHE
    if _ALL_ROWS_CACHE is None:
        with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
            cur.execute("SELECT name, description FROM mushrooms;")
            _ALL_ROWS_CACHE = cur.fetchall()
    return _ALL_ROWS_CACHE


# --- Retrieval -----------------------------------------------------------
# Surowy chunk: (name, desc, score). Wynik retrieve(): dict {name -> {chunks, agg_score}}.

def _vec(question: str) -> list[float]:
    return embedder.encode(question, normalize_embeddings=True).tolist()


def _to_sim(metric: str, dist: float) -> float:
    if metric == "cosine":
        return 1.0 - dist
    return 1.0 / (1.0 + dist)


def retrieve_pgvector_chunks(question: str, fetch: int, metric: str) -> List[Tuple[str, str, float]]:
    """Pobiera `fetch` surowych chunków posortowanych po wybranej metryce."""
    op = PGV_OP[metric]
    vec = _vec(question)
    sql = f"""
=======


# --- Retrieval ------------------------------------------------------------
def retrieve(question: str, k: int = TOP_K):
    response = ollama.embeddings(model=EMBED_MODEL_NAME, prompt=question)
    vec = response['embedding']
    
    sql = """
>>>>>>> 227926647e68554d02d59847857acef1fe841fdc
        SELECT name, description,
               (embedding {op} %s::vector) AS dist
        FROM mushrooms
        ORDER BY embedding {op} %s::vector
        LIMIT %s;
    """
<<<<<<< HEAD
    try:
        with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
            cur.execute(sql, (str(vec), str(vec), fetch))
            rows = cur.fetchall()
    except psycopg2.Error:
        if metric == "l1":
            return retrieve_numeric_client_side(question, fetch, "l1")
        raise

    return [(name, desc, _to_sim(metric, float(dist))) for name, desc, dist in rows]
=======
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            vec_str = str(vec)
            cur.execute(sql, (vec_str, vec_str, k))
            return cur.fetchall()  # [(name, description, similarity), ...]
>>>>>>> 227926647e68554d02d59847857acef1fe841fdc


def retrieve_numeric_client_side(question: str, fetch: int, metric: str) -> List[Tuple[str, str, float]]:
    """Fallback dla L1: liczymy w Pythonie. Uwaga – pobiera wszystkie embeddingi."""
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT name, description, embedding FROM mushrooms;")
        full = cur.fetchall()

    q_vec = np.asarray(embedder.encode(question, normalize_embeddings=True), dtype=np.float32)
    scored: list[tuple[str, str, float]] = []
    for name, desc, emb in full:
        if isinstance(emb, str):
            vec = np.fromstring(emb.strip("[]"), sep=",", dtype=np.float32)
        else:
            vec = np.asarray(emb, dtype=np.float32)
        if metric == "l1":
            dist = float(np.abs(q_vec - vec).sum())
        elif metric == "l2":
            dist = float(np.linalg.norm(q_vec - vec))
        else:
            denom = (np.linalg.norm(q_vec) * np.linalg.norm(vec)) or 1.0
            scored.append((name, desc, float(q_vec @ vec) / denom))
            continue
        scored.append((name, desc, 1.0 / (1.0 + dist)))

    scored.sort(key=lambda r: r[2], reverse=True)
    return scored[:fetch]


def retrieve_jaccard_chunks(question: str, fetch: int) -> List[Tuple[str, str, float]]:
    """Jaccard na zbiorach tokenów – działa na pełnym cache chunków."""
    rows = load_all_rows()
    q_tokens = tokenize(question)
    if not q_tokens:
        return []
    scored: list[tuple[str, str, float]] = []
    for name, desc in rows:
        d_tokens = tokenize(desc)
        if not d_tokens:
            continue
        inter = len(q_tokens & d_tokens)
        if inter == 0:
            continue
        union = len(q_tokens | d_tokens)
        scored.append((name, desc, inter / union))
    scored.sort(key=lambda r: r[2], reverse=True)
    return scored[:fetch]


def name_match_in_question(question: str, max_hits: int = 3) -> list[str]:
    """Zwraca listę unikalnych wartości kolumny `name`, których polska albo łacińska
    nazwa pojawia się w pytaniu (pełna lub w >=70% słów)."""
    q_norm = strip_accents(question.lower())
    q_words = set(q_norm.split())
    hits: list[tuple[str, int]] = []  # (name, długość dopasowania)
    for name in load_unique_names():
        pol = extract_polish_name(name) or ""
        lat = extract_latin_name(name) or ""
        for cand in {pol, lat, name}:
            cand_norm = strip_accents(cand.lower()).strip()
            if len(cand_norm) < 4:
                continue
            if cand_norm in q_norm:
                hits.append((name, len(cand_norm)))
                break
            cand_words = set(cand_norm.split())
            if len(cand_words) >= 2:
                overlap = len(cand_words & q_words)
                if overlap >= max(1, len(cand_words) * 0.7):
                    hits.append((name, len(cand_norm) // 2))
                    break

    # dłuższe dopasowania są bardziej specyficzne (np. "muchomor sromotnikowy" > "muchomor")
    hits.sort(key=lambda h: h[1], reverse=True)
    seen, out = set(), []
    for name, _ in hits:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= max_hits:
            break
    return out


def fetch_chunks_for_species(species_names: list[str]) -> list[tuple[str, str]]:
    if not species_names:
        return []
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT name, description FROM mushrooms WHERE name = ANY(%s);",
            (list(species_names),),
        )
        return cur.fetchall()


def group_by_species(rows: List[Tuple[str, str, float]]) -> "OrderedDict[str, dict]":
    """Grupuje chunki po `name`. Score gatunku = suma score najlepszych chunków + bonus za liczbę trafień."""
    groups: dict[str, dict] = {}
    for name, desc, sim in rows:
        g = groups.setdefault(name, {"chunks": [], "sum_score": 0.0, "best_score": 0.0, "n": 0})
        g["chunks"].append((desc, sim))
        g["sum_score"] += sim
        g["best_score"] = max(g["best_score"], sim)
        g["n"] += 1

    # finalny score: najlepszy chunk + log-bonus za liczbę trafień
    for g in groups.values():
        g["chunks"].sort(key=lambda c: c[1], reverse=True)
        g["score"] = g["best_score"] + 0.05 * np.log1p(g["n"])

    return OrderedDict(
        sorted(groups.items(), key=lambda kv: kv[1]["score"], reverse=True)
    )


def retrieve(question: str, k: int, metric: str) -> Tuple["OrderedDict[str, dict]", str | None]:
    """Hybrydowe pobieranie. Zwraca (grupy_po_gatunku, temat).

    Strategia:
    1. Jeśli w pytaniu pojawia się nazwa gatunku → pobierz WSZYSTKIE chunki tego
       gatunku (1-2 gatunki) i to jest cały kontekst. Topic ustawiony.
    2. W przeciwnym razie pobierz dużo chunków po wybranej metryce, zgrupuj po
       gatunku, weź top-k różnych gatunków.
    """
    matched = name_match_in_question(question, max_hits=2)
    if matched:
        rows = fetch_chunks_for_species(matched)
        # nadaj sztuczne score = 1.0 dla wszystkich chunków – kontekst ograniczony do tych gatunków
        scored_rows = [(n, d, 1.0) for n, d in rows]
        # zachowaj kolejność z `matched`
        groups = group_by_species(scored_rows)
        ordered = OrderedDict(
            (n, groups[n]) for n in matched if n in groups
        )
        primary = matched[0]
        topic = primary  # już w formacie "Polska (Latin)"
        return ordered, topic

    fetch = max(FETCH_MULTIPLIER * k, 40)
    if metric == "jaccard":
        raw = retrieve_jaccard_chunks(question, fetch)
    else:
        raw = retrieve_pgvector_chunks(question, fetch, metric)

    groups = group_by_species(raw)
    # weź top-k gatunków
    top = OrderedDict(list(groups.items())[:k])
    return top, None


# --- Kontekst i LLM ------------------------------------------------------
def build_context(groups: "OrderedDict[str, dict]") -> str:
    blocks: list[str] = []
    total = 0
    for idx, (name, g) in enumerate(groups.items(), 1):
        pol = extract_polish_name(name) or name
        lat = extract_latin_name(name) or ""
        header = f"[{idx}] {pol}" + (f" ({lat})" if lat else "")

        # sklej najlepsze chunki, dedup po treści
        seen_text, parts = set(), []
        used = 0
        for desc, _ in g["chunks"][:MAX_CHUNKS_PER_SPECIES]:
            d = (desc or "").strip()
            if not d:
                continue
            # dedup po pierwszych 80 znakach
            key = d[:80]
            if key in seen_text:
                continue
            seen_text.add(key)
            if used + len(d) > MAX_CTX_CHARS_PER_SPECIES:
                d = d[: MAX_CTX_CHARS_PER_SPECIES - used]
            parts.append(d)
            used += len(d)
            if used >= MAX_CTX_CHARS_PER_SPECIES:
                break

        block = header + "\n" + "\n\n".join(parts)
        if total + len(block) > MAX_CTX_CHARS_TOTAL:
            break
        blocks.append(block)
        total += len(block)

    separator = "\n\n" + "=" * 60 + "\n\n"
    return separator.join(blocks)


def ask_llm(question: str, context: str, topic: str | None = None) -> None:
    topic_line = f"TEMAT: {topic}\n\n" if topic else "TEMAT: (brak – użyj bloku [1])\n\n"
    user_msg = (
        f"{topic_line}"
        f"PYTANIE: {question}\n\n"
        "KONTEKST (fragmenty bazy o grzybach – każdy blok dotyczy JEDNEGO gatunku):\n\n"
        f"{context}\n\n"
        "Odpowiedz na PYTANIE, opisując WYŁĄCZNIE gatunek wskazany w TEMAT "
        "(albo z bloku [1], gdy TEMAT pusty). Inne gatunki z kontekstu zignoruj."
    )
    stream = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        stream=True,
        options={"temperature": 0.1, "num_ctx": 8192, "top_p": 0.9, "repeat_penalty": 1.1},
    )
    for chunk in stream:
        token = chunk.get("message", {}).get("content", "")
        print(token, end="", flush=True)
    print()


# --- CLI -----------------------------------------------------------------
HELP_TEXT = (
    "Komendy:\n"
    "  /metric <cosine|l1|l2|jaccard>   – zmiana metryki podobieństwa\n"
    "  /topk <n>                        – ile dokumentów pobierać (1-15)\n"
    "  /show                            – pokaż aktualne ustawienia\n"
    "  /help                            – ta pomoc\n"
    "  q | quit | exit | wyjscie        – zakończ"
)


def banner(metric: str, topk: int) -> None:
    print("\n" + "=" * 60)
    print("  GRZYBO-BOT (RAG + lokalna Gemma)")
    print(f"  Model LLM : {LLM_MODEL}")
    print(f"  Embedder  : {EMBED_MODEL_NAME}")
    print(f"  Metryka   : {metric}   |   TOP_K: {topk}")
    print("  Wpisz /help aby zobaczyć komendy, q aby wyjść.")
    print("=" * 60)


def prompt_metric_at_start() -> str:
    print("\nDostępne metryki: cosine, l1, l2, jaccard")
    try:
        raw = input(f"Wybierz metrykę [{DEFAULT_METRIC}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return DEFAULT_METRIC
    if not raw:
        return DEFAULT_METRIC
    if raw not in VALID_METRICS:
        print(f"[uwaga] Nieznana metryka '{raw}', używam '{DEFAULT_METRIC}'.")
        return DEFAULT_METRIC
    return raw


def handle_command(cmd: str, state: dict) -> bool:
    """Obsługuje polecenia zaczynające się od '/'. Zwraca True jeśli to była komenda."""
    if not cmd.startswith("/"):
        return False
    parts = cmd.split()
    head = parts[0].lower()
    if head == "/help":
        print(HELP_TEXT)
    elif head == "/show":
        print(f"metric={state['metric']}, top_k={state['top_k']}, model={LLM_MODEL}")
    elif head == "/metric":
        if len(parts) < 2 or parts[1].lower() not in VALID_METRICS:
            print(f"Użycie: /metric <{'|'.join(sorted(VALID_METRICS))}>")
        else:
            state["metric"] = parts[1].lower()
            print(f"[ok] metryka = {state['metric']}")
    elif head == "/topk":
        try:
            n = int(parts[1])
            if not 1 <= n <= 15:
                raise ValueError
            state["top_k"] = n
            print(f"[ok] top_k = {n}")
        except (IndexError, ValueError):
            print("Użycie: /topk <liczba 1-15>")
    else:
        print(f"Nieznana komenda: {head}. Wpisz /help.")
    return True


def main() -> int:
    metric = prompt_metric_at_start()
    state = {"metric": metric, "top_k": DEFAULT_TOP_K}

    # rozgrzewka cache nazw – żeby pierwsze pytanie nie czekało na DISTINCT
    try:
        names = load_unique_names()
        print(f"[init] Unikalnych gatunków w bazie: {len(names)}", file=sys.stderr)
    except psycopg2.Error as e:
        print(f"[błąd DB przy starcie] {e}", file=sys.stderr)
        return 1

    banner(state["metric"], state["top_k"])

    while True:
        try:
            q = input("\nTy: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.lower() in {"q", "quit", "exit", "wyjscie"}:
            break
        if handle_command(q, state):
            continue

        try:
            groups, topic = retrieve(q, state["top_k"], state["metric"])
        except psycopg2.Error as e:
            print(f"[błąd DB] {e}")
            continue
        except Exception as e:
            print(f"[błąd retrieval] {e}")
            continue

        if not groups:
            print("Bot: Nie znalazłem nic w bazie.")
            continue

        print("Bot: ", end="", flush=True)
        try:
            ask_llm(q, build_context(groups), topic=topic)
        except Exception as e:
            print(f"\n[błąd LLM] {e}\nCzy Ollama jest uruchomiona i model '{LLM_MODEL}' pobrany?")

    return 0


if __name__ == "__main__":
    sys.exit(main())
