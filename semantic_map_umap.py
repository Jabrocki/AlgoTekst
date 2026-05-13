import psycopg2
import numpy as np
import re
import pandas as pd
import plotly.express as px
import umap
from sklearn.cluster import KMeans
from scipy.spatial.distance import cdist

DB_URL = "postgresql://postgres.vhwxrmwtekxelbarhcgl:grzyby12345!!!@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"


def fetch_data():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT name, embedding, description FROM mushrooms;")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


def create_3d_scatter_plots(data):
    display_names = []
    embeddings = []

    for d in data:
        raw_name = d[0]
        raw_embedding = d[1]
        description = d[2] if d[2] else ""

        match = re.search(r"polish_name:\s*([^\n\r]+)", description, re.IGNORECASE)
        if match:
            display_names.append(match.group(1).strip())
        else:
            display_names.append(raw_name)

        if isinstance(raw_embedding, str):
            clean_val = re.findall(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?", raw_embedding)
            vec = np.array(clean_val, dtype=np.float32)
        else:
            vec = np.array(raw_embedding, dtype=np.float32)
        embeddings.append(vec)

    X = np.array(embeddings)
    X_bin = (X > 0).astype(int)

    kmeans = KMeans(n_clusters=50, n_init="auto", random_state=6)
    clusters = kmeans.fit_predict(X)
    cluster_labels = [f"Grupa {c+1}" for c in clusters]

    metrics_to_test = {
        "l2": cdist(X, X, metric="euclidean"),
        "l1": cdist(X, X, metric="cityblock"),
        "cosine": cdist(X, X, metric="cosine"),
        "jaccard": cdist(X_bin, X_bin, metric="jaccard"),
    }

    for metric_name, dist_matrix in metrics_to_test.items():
        print(
            f"Generowanie 3D Scatter Plot (UMAP) dla metryki: {metric_name.upper()}..."
        )

        reducer = umap.UMAP(
            n_components=3,
            metric="precomputed",
            n_neighbors=12,
            min_dist=0.1,
            random_state=420,
        )
        X_3d = reducer.fit_transform(dist_matrix)

        df = pd.DataFrame(
            {
                "X": X_3d[:, 0],
                "Y": X_3d[:, 1],
                "Z": X_3d[:, 2],
                "Grzyb": display_names,
                "Rodzina": cluster_labels,
            }
        )

        fig = px.scatter_3d(
            df,
            x="X",
            y="Y",
            z="Z",
            color="Rodzina",
            hover_name="Grzyb",
            title=f"Kosmos Grzybów 3D UMAP (Metryka: {metric_name.upper()})",
            template="plotly_dark",
            color_discrete_sequence=px.colors.qualitative.Alphabet,
        )

        fig.update_traces(
            marker=dict(
                size=2.5, opacity=0.9, line=dict(width=0.2, color="DarkSlateGrey")
            )
        )

        fig.update_layout(
            showlegend=False,
            scene=dict(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                zaxis=dict(visible=False),
            ),
            margin=dict(l=0, r=0, b=0, t=40),
        )

        output_file = f"scatter_3d_umap_{metric_name}.html"
        fig.write_html(output_file)
        print(f"Zapisano wizualizację do: {output_file}")


if __name__ == "__main__":
    print("Pobieranie danych...")
    mushrooms = fetch_data()

    if not mushrooms:
        print("Brak danych w bazie!")
    else:
        create_3d_scatter_plots(mushrooms)
