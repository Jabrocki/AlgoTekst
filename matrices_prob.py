import psycopg2
import numpy as np
import pandas as pd
import re

from scipy.spatial.distance import cdist

DB_URL = (
    "postgresql://postgres.vhwxrmwtekxelbarhcgl:grzyby12345!!!"
    "@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
)


def fetch_embeddings():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    cur.execute("SELECT name, embedding FROM mushrooms;")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    names = []
    vectors = []

    for name, embedding in rows:
        try:
            if embedding is None:
                continue

            if isinstance(embedding, str):
                cleaned = embedding.strip("[]")
                vec = np.fromstring(cleaned, sep=",", dtype=np.float32)
            else:
                vec = np.array(embedding, dtype=np.float32)

            if vec.size == 0:
                continue

            names.append(name)
            vectors.append(vec)

        except Exception as e:
            print(f"Błąd przy {name}: {e}")

    X = np.array(vectors, dtype=np.float32)

    print("Shape:", X.shape)

    return names, X

def build_matrix(X, metric):
    if metric == "jaccard":
        X = (X > 0).astype(int)
        matrix = cdist(X, X, metric="jaccard")
    else:
        matrix = cdist(X, X, metric=metric)

    np.fill_diagonal(matrix, 0)

    return matrix


def save_matrix(matrix, names, filename):
    df = pd.DataFrame(matrix, index=names, columns=names)
    df.to_csv(filename)


def main():
    names, X = fetch_embeddings()

    metrics = {
        "cosine": "cosine",
        "l1": "cityblock",
        "l2": "euclidean",
        "jaccard": "jaccard",
    }

    for label, metric in metrics.items():
        matrix = build_matrix(X, metric)
        save_matrix(matrix, names, f"{label}_matrix.csv")


if __name__ == "__main__":
    main()