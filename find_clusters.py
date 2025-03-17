import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from sklearn.cluster import KMeans
from sklearn.metrics import pairwise_distances_argmin_min
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import pymongo

load_dotenv()

# Connect to MongoDB
MONGO_URI = os.getenv("MONGODB_URI")
client = pymongo.MongoClient(MONGO_URI)
db = client["techcrunch_db"]
collection = db["top_stories"]

# Extract _id, numeric_response, and additional metadata
print("Extracting _id and numeric_response data from MongoDB...")
stories = []
for story in collection.find({"numeric_response": {"$exists": True}},
                             {"_id": 1, "numeric_response": 1, "title": 1, "link": 1,
                              "published": 1, "summary": 1, "article_ID": 1, "duration": 1, "authors": 1}):
    if isinstance(story["numeric_response"], dict):  # Ensure it's a dictionary
        numeric_values = [val for val in story["numeric_response"].values() if val is not None]  # Remove None values
        if len(numeric_values) == len(story["numeric_response"]):
            stories.append({
                "_id": story["_id"],
                "numeric_response": numeric_values,
                "title": story.get("title"),
                "link": story.get("link"),
                "published": story.get("published"),
                "summary": story.get("summary"),
                "article_ID": story.get("article_ID"),
                "duration": story.get("duration"),
                "authors": story.get("authors")
            })

print(f"Extracted {len(stories)} cleaned documents.")

# Convert to a DataFrame
numeric_df = pd.DataFrame(stories)

# Drop NaN values if any
if numeric_df.isnull().values.any():
    print("NaN values detected in the DataFrame. Dropping NaNs...")
    numeric_df = numeric_df.dropna()
print(f"DataFrame size after dropping NaN values: {numeric_df.shape}")



# Convert numeric_response column to a NumPy array
numeric_array = np.vstack(numeric_df["numeric_response"].values)


###
###USING AI MADE PERSONAS
# Define custom starting centroids
initial_centroids = np.array([
    [1, 1, 3, 3, 4, 1, 3, 3, 1, 1, 3],  # DATA-DRIVEN Analyst
    [4, 4, 3, 4, 4, 4, 3, 3, 4, 4, 3],  # Engaging Storyteller
    [2, 2, 3, 3, 4, 2, 3, 3, 2, 2, 3],  # Critical Thinker
    [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]   # Balanced Evaluator
])
# K-means clustering with predefined centroids
k = 4
kmeans = KMeans(n_clusters=k, init=initial_centroids, n_init=1, random_state=42)
kmeans.fit(numeric_array)
labels = kmeans.labels_
centroids = kmeans.cluster_centers_

# Compute error (inertia)
error = kmeans.inertia_
print(f"K-Means clustering error (inertia): {error}")

# Apply PCA for visualization
pca = PCA(n_components=2)
reduced_data = pca.fit_transform(numeric_array)
centroids_2d = pca.transform(centroids)

# Plot PCA clusters
plt.figure(figsize=(8, 6))
scatter = plt.scatter(reduced_data[:, 0], reduced_data[:, 1], c=labels, cmap='viridis', alpha=0.6, edgecolors='k')
plt.scatter(centroids_2d[:, 0], centroids_2d[:, 1], c='red', marker='X', s=200, label='Centroids')
plt.xlabel('Principal Component 1')
plt.ylabel('Principal Component 2')
plt.title(f'K-Means Clustering Visualization (PCA, k={k})')
plt.legend()
plt.grid(True)
plt.show()

print("K-Means clustering with predefined centroids completed.")


###USING ML DETERMINED PERSONAS

# Try different numbers of clusters (k)
k_values = range(2, 11)  # Vary k from 2 to 10
errors = []
centroids_list = []

print("Running K-Means clustering...")
for k in k_values:
    kmeans = KMeans(n_clusters=k, init="random", n_init=10, random_state=42)
    kmeans.fit(numeric_array)
    error = kmeans.inertia_  # Sum of squared distances to closest cluster center
    errors.append(error)
    centroids_list.append(kmeans.cluster_centers_)
    print(f"K={k}, Error={error}")
    print(f"Centroids for K={k}:\n{kmeans.cluster_centers_}\n")

# Plot the elbow curve
plt.figure(figsize=(8, 5))
plt.plot(k_values, errors, marker='o', linestyle='-', color='b')
plt.xlabel('Number of Clusters (k)')
plt.ylabel('Sum of Squared Distances (Error)')
plt.title('Elbow Curve for K-Means Clustering')
plt.grid(True)
plt.show()

print("K-Means clustering completed.")


# Choose optimal k based on elbow curve (assuming k=4 for visualization)
k = 4
kmeans = KMeans(n_clusters=k, init="random", n_init=10, random_state=42)
kmeans.fit(numeric_array)
labels = kmeans.labels_
centroids = kmeans.cluster_centers_

# Apply PCA for visualization
pca = PCA(n_components=2)
reduced_data = pca.fit_transform(numeric_array)
centroids_2d = pca.transform(centroids)

# Plot PCA clusters
plt.figure(figsize=(8, 6))
scatter = plt.scatter(reduced_data[:, 0], reduced_data[:, 1], c=labels, cmap='viridis', alpha=0.6, edgecolors='k')
plt.scatter(centroids_2d[:, 0], centroids_2d[:, 1], c='red', marker='X', s=200, label='Centroids')
plt.xlabel('Principal Component 1')
plt.ylabel('Principal Component 2')
plt.title(f'K-Means Clustering Visualization (PCA, k={k})')
plt.legend()
plt.grid(True)
plt.show()

# Apply t-SNE for visualization
tsne = TSNE(n_components=2, perplexity=30, random_state=42)
tsne_results = tsne.fit_transform(numeric_array)

# Plot t-SNE clusters
plt.figure(figsize=(8, 6))
scatter = plt.scatter(tsne_results[:, 0], tsne_results[:, 1], c=labels, cmap='viridis', alpha=0.6, edgecolors='k')
plt.xlabel('t-SNE Component 1')
plt.ylabel('t-SNE Component 2')
plt.title(f'K-Means Clustering Visualization (t-SNE, k={k})')
plt.legend()
plt.grid(True)
plt.show()

print("K-Means clustering and visualization (PCA & t-SNE) completed.")


