import os
import glob
import re
import ollama
import psycopg2
from psycopg2.extras import execute_batch
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def read_markdown_files(directory_path="./data"):
    mushrooms_chunks = []
    search_pattern = os.path.join(directory_path, "*.md")
    
    for filepath in glob.glob(search_pattern):
        filename = os.path.basename(filepath)
        latin_name_from_file = os.path.splitext(filename)[0].replace("_", " ").title() 
        
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                
            if not content:
                continue

            pl_name_match = re.search(r'polish_name:\s*([^\n]+)', content)
            if pl_name_match:
                polish_name = pl_name_match.group(1).split(',')[0].strip()
                mushroom_label = f"{polish_name} ({latin_name_from_file})"
            else:
                mushroom_label = latin_name_from_file

            # CZYSZCZENIE TEKSTU ZE ŚMIECI
            # Usuwamy bloki --- ... --- (metadane)
            content_clean = re.sub(r'(?s)---.*?---', '', content)
            
            # WYCINANIE CHUNKÓW (fragmentów)
            lines = content_clean.split('\n')
            current_heading = "Informacje ogólne"
            current_text = []

            for line in lines:
                line_stripped = line.strip()
                
                if not line_stripped:
                    continue
                
                if line_stripped.startswith('#') and ' ' not in line_stripped:
                    continue

                heading_match = re.match(r'^(#+)\s+(.*)', line_stripped)
                
                if heading_match:
                    if current_text:
                        text_joined = "\n".join(current_text).strip()
                        if len(text_joined) > 30:
                            chunk_text = f"{mushroom_label} - {current_heading}: {text_joined}"
                            mushrooms_chunks.append({
                                "name": mushroom_label, 
                                "description": chunk_text
                            })
                    
                    current_heading = heading_match.group(2).strip()
                    current_text = []
                else:
                    current_text.append(line_stripped)
            
            if current_text:
                text_joined = "\n".join(current_text).strip()
                if len(text_joined) > 30:
                    chunk_text = f"{mushroom_label} - {current_heading}: {text_joined}"
                    mushrooms_chunks.append({
                        "name": mushroom_label, 
                        "description": chunk_text
                    })
                    
        except Exception as e:
            print(f"Błąd czytania pliku {filename}: {e}")

    return mushrooms_chunks


def generate_embedding(text):
    delay = 3
    retries = 3
    for attempt in range(retries):
        try:
            response = ollama.embeddings(model='nomic-embed-text', prompt=text)
            return response['embedding']
        except Exception as e:
                print(f"Zadławienie modelu (próba {attempt + 1}/{retries}): {e}. Czekam {delay}s...")
                time.sleep(delay)
            
    print("Nie udało się wygenerować wektora po kilku próbach. Pomijam chunk.")
    return None

def main():
    print("\n1. Odczytywanie plików z ./data")
    mushrooms_data = read_markdown_files("./data")
    
    if not mushrooms_data:
        print("Nie znaleziono danych")
        return
        
    print(f"Znaleziono {len(mushrooms_data)} sensownych kawałków (chunków). Rozpoczynam generowanie wektorów.")
    records_to_insert = []
    
    start_time = time.time()

    # Funkcja pomocnicza dla wielowątkowości
    def process_chunk(item):
        emb = generate_embedding(item['description'])
        if emb:
            return (item['name'], item['description'], emb)
        return None

    print("Mielenie danych przez model Ollama (wielowątkowo)...")
    
    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        przyszle_zadania = {executor.submit(process_chunk, item): item for item in mushrooms_data}
        
        licznik = 0
        for future in as_completed(przyszle_zadania):
            licznik += 1
            
            wynik = future.result()
            results.append(wynik)
            
            if licznik % 100 == 0:
                print(f"Postęp: Przetworzono {licznik} z {len(mushrooms_data)} wektorów...")
    
    records_to_insert = [r for r in results if r is not None]
    
    end_time = time.time()
    print(f"Generowanie wektorów zajęło: {round((end_time - start_time) / 60, 2)} minut.")
    # ----------------------------------------------------

    if not records_to_insert:
        print("Nie wygenerowano wektorów")
        return

    # zapis do bazy
    print(f"\n3. Łączenie z bazą, zapisywanie {len(records_to_insert)} rekordów")
    conn = None
    cur = None
    
    try:
        conn = psycopg2.connect(
            "postgresql://postgres.vhwxrmwtekxelbarhcgl:grzyby12345!!!@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
        )
        cur = conn.cursor()

        insert_query = """
            INSERT INTO mushrooms (name, description, embedding)
            VALUES (%s, %s, %s)
        """
        BATCH_SIZE = 500
        
        for i in range(0, len(records_to_insert), BATCH_SIZE):
            batch = records_to_insert[i:i + BATCH_SIZE]
            
            # Wrzucamy paczkę do bazy
            execute_batch(cur, insert_query, batch)
            
            # Zatwierdzamy transakcję od razu po każdej paczce
            conn.commit() 
            
            print(f"Zapisano w bazie: {i + len(batch)} / {len(records_to_insert)} rekordów...")

        print("Wszystkie dane wylądowały w bazie")

    except psycopg2.Error as e:
        print(f"Błąd zapisu do bazy danych: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()
            print("Połączenie z bazą zamknięte.")

if __name__ == "__main__":
    main()