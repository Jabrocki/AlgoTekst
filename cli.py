import psycopg2
import ollama

print("Ładowanie modelu językowego (to może potrwać chwilę)...")

DB_URL = "postgresql://postgres.vhwxrmwtekxelbarhcgl:grzyby12345!!!@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"


def get_answer_from_db(question):
    try:
        response = ollama.embeddings(model='nomic-embed-text', prompt=question)
        query_vector = response['embedding']
    except Exception as e:
        return f"Błąd przetwarzania pytania: {e}"

    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        search_query = """
            WITH top_matches AS (
                SELECT 
                    name, 
                    description, 
                    embedding <=> %s::vector AS distance
                FROM mushrooms
                ORDER BY distance
                LIMIT 50
            ),
            ranked_matches AS (
                SELECT 
                    name, 
                    description, 
                    distance,
                    ROW_NUMBER() OVER(PARTITION BY name ORDER BY distance) as rn
                FROM top_matches
            )
            SELECT name, description 
            FROM ranked_matches
            WHERE rn = 1
            ORDER BY distance
            LIMIT 3;
        """

        # Wrzucamy listę liczb jako string (np. '[0.1, 0.2, ...]') do zapytania SQL
        cur.execute(search_query, (str(query_vector),))
        results = cur.fetchall()

        return results

    except psycopg2.Error as e:
        return f"Błąd bazy danych: {e}"
    finally:
        if conn:
            cur.close()
            conn.close()


def start_cli():
    print("\n" + "=" * 50)
    print("🍄 WITAJ W GRZYBO-BOCIE! 🍄")
    print("Zadaj pytanie, a poszukam odpowiedzi w mojej bazie.")
    print("Wpisz 'wyjscie' lub 'q', aby zamknąć program.")
    print("=" * 50 + "\n")

    while True:
        pytanie = input("\nTy: ")

        if pytanie.lower() in ['wyjscie', 'q', 'quit', 'exit']:
            print("Grzybo-Bot: Do zobaczenia w lesie! 🌲")
            break

        if not pytanie.strip():
            continue

        print("Grzybo-Bot: Przeszukuję las... (szukam w bazie)")

        wyniki = get_answer_from_db(pytanie)

        if isinstance(wyniki, str):
            print(f"Grzybo-Bot: Ups! Coś poszło nie tak. {wyniki}")
        elif not wyniki:
            print("Grzybo-Bot: Niestety nic nie znalazłem na ten temat.")
        else:
            print("\nGrzybo-Bot: Oto co znalazłem:\n")
            for i, (nazwa, opis) in enumerate(wyniki, 1):
                print(f"--- Wynik {i}: {nazwa} ---")
                skrocony_opis = opis[:300] + "..." if len(opis) > 300 else opis
                print(f"{skrocony_opis}\n")


if __name__ == "__main__":
    start_cli()