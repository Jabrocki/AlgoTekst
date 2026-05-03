import os
import glob
import psycopg2
from psycopg2.extras import execute_batch
from sentence_transformers import SentenceTransformer

# inicjalizacja lokalnego modelu
model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')

def read_markdown_files(directory_path="./data"):
    mushrooms = []
    search_pattern = os.path.join(directory_path, "*.md")
    
    for filepath in glob.glob(search_pattern):
        filename = os.path.basename(filepath)
        name = os.path.splitext(filename)[0]
        clean_name = name.replace("_", " ").title()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                description = file.read().strip()
                
            if description:
                mushrooms.append({"name": clean_name, "description": description})
        except Exception as e:
            print(f"Błąd czytania pliku {filename}: {e}")
            
    return mushrooms

def generate_embedding(text):
    try:
        # .encode() zamienia tekst na wektor (numpy array)
        vector = model.encode(text)
        return vector.tolist()
    except Exception as e:
        print(f"Błąd modelu: {e}")
        return None

def main():
    print("\nodczytywanie plików z ./data")
    mushrooms_data = read_markdown_files("./data")
    
    if not mushrooms_data:
        print("nie znaleziono danych")
        return
        
    print(f"znaleziono {len(mushrooms_data)} plików, rozpoczynam generowanie wektorów")
    records_to_insert = []
    
    # generowanie wektorów
    for idx, item in enumerate(mushrooms_data, 1):
        # Wypisujemy postęp co 100 plików
        if idx % 100 == 0 or idx == len(mushrooms_data):
            print(f"Przetworzono {idx}/{len(mushrooms_data)} grzybów...")
            
        embedding = generate_embedding(item['description'])
        
        if embedding:
            records_to_insert.append((item['name'], item['description'], embedding))

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
        execute_batch(cur, insert_query, records_to_insert)
        
        conn.commit()
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