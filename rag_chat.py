"""
RAG-chat o grzybach: retrieval z pgvector (Supabase) + generacja przez lokalną Gemmę (Ollama).

Uruchom:
    python rag_chat.py
Wymagania:
    1. Ollama uruchomiona w tle (instalator z https://ollama.com).
    2. Pobranie modeli:  
       ollama pull gemma3:4b
       ollama pull nomic-embed-text
    3. pip install -r requirements.txt
"""

import os
import sys
import psycopg2
import ollama
from sentence_transformers import SentenceTransformer

# --- Konfiguracja ---------------------------------------------------------
DB_URL = os.getenv(
    "MUSHROOM_DB_URL",
    "postgresql://postgres.vhwxrmwtekxelbarhcgl:grzyby12345!!!"
    "@aws-0-eu-west-1.pooler.supabase.com:6543/postgres",
)
EMBED_MODEL_NAME = "nomic-embed-text"
LLM_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")  # zmień na gemma3:1b jeżeli mało RAM
TOP_K = 4               # ile fragmentów wciągamy do kontekstu
MAX_CTX_CHARS = 2500    # przycinanie pojedynczego opisu, by nie zalać promptu

SYSTEM_PROMPT = (
    "Jesteś ekspertem mykologiem. Odpowiadaj wyłącznie po polsku, rzeczowo i krótko. "
    "Bazuj WYŁĄCZNIE na fragmentach z kontekstu poniżej. "
    "Jeśli kontekst nie zawiera odpowiedzi, powiedz wprost: 'Nie mam tej informacji w bazie.' "
    "Na końcu odpowiedzi dodaj listę użytych grzybów w nawiasach kwadratowych, np. [Pieczarka biaława]. "
    "Nigdy nie zachęcaj do spożywania grzybów bez weryfikacji u eksperta."
)



# --- Retrieval ------------------------------------------------------------
def retrieve(question: str, k: int = TOP_K):
    response = ollama.embeddings(model=EMBED_MODEL_NAME, prompt=question)
    vec = response['embedding']
    
    sql = """
        SELECT name, description,
               1 - (embedding <=> %s::vector) AS similarity
        FROM mushrooms
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            vec_str = str(vec)
            cur.execute(sql, (vec_str, vec_str, k))
            return cur.fetchall()  # [(name, description, similarity), ...]


def build_context(rows) -> str:
    chunks = []
    for name, desc, sim in rows:
        snippet = desc[:MAX_CTX_CHARS]
        chunks.append(f"### {name}  (podobieństwo: {sim:.2f})\n{snippet}")
    return "\n\n".join(chunks)


# --- Generacja ------------------------------------------------------------
def ask_llm(question: str, context: str):
    user_msg = (
        f"KONTEKST (fragmenty bazy o grzybach):\n{context}\n\n"
        f"PYTANIE UŻYTKOWNIKA:\n{question}"
    )
    stream = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        stream=True,
        options={"temperature": 0.2, "num_ctx": 8192},
    )
    for chunk in stream:
        token = chunk.get("message", {}).get("content", "")
        print(token, end="", flush=True)
    print()


# --- CLI ------------------------------------------------------------------
def main():
    print("\n" + "=" * 50)
    print("🍄  GRZYBO-BOT (RAG + Gemma lokalnie)")
    print(f"Model LLM: {LLM_MODEL}   |   TOP_K: {TOP_K}")
    print("Wpisz 'q' aby wyjść.")
    print("=" * 50)

    while True:
        try:
            q = input("\nTy: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.lower() in {"q", "quit", "exit", "wyjscie"}:
            break
        if not q:
            continue

        try:
            rows = retrieve(q)
        except psycopg2.Error as e:
            print(f"[błąd DB] {e}")
            continue

        if not rows:
            print("Bot: Nie znalazłem nic w bazie.")
            continue

        print("Bot: ", end="", flush=True)
        try:
            ask_llm(q, build_context(rows))
        except Exception as e:
            print(f"\n[błąd LLM] {e}\nCzy Ollama jest uruchomiona i model '{LLM_MODEL}' pobrany?")


if __name__ == "__main__":
    sys.exit(main())
