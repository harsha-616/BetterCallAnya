import fitz  # PyMuPDF
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv

load_dotenv()

pdf_path = "medical_data.pdf"
chroma_dir = os.getenv("CHROMA_DB_PATH", "chroma.sqlite3")

# We will use the directory chroma.sqlite3 (even if the name has an extension, chromadb just creates a folder)
print(f"Initializing ChromaDB at {chroma_dir}...")
client = chromadb.PersistentClient(path=chroma_dir)

embedding_model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
print(f"Loading embedding model: {embedding_model_name}")
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=embedding_model_name)

collection = client.get_or_create_collection(name="medical_docs", embedding_function=ef)

print(f"Reading {pdf_path}...")
try:
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
except Exception as e:
    print(f"Failed to read PDF: {e}")
    exit(1)

print("Chunking text...")
chunk_size = 1000
overlap = 200
chunks = []
for i in range(0, len(text), chunk_size - overlap):
    chunks.append(text[i:i + chunk_size])

print(f"Total chunks from text calculation: {len(chunks)}.")

existing_count = collection.count()
print(f"Existing chunks already in ChromaDB: {existing_count}")

batch_size = 100
for i in range(existing_count, len(chunks), batch_size):
    batch = chunks[i:i + batch_size]
    ids = [f"chunk_{i + j}" for j in range(len(batch))]
    metadatas = [{"source": pdf_path} for _ in batch]
    collection.add(
        documents=batch,
        metadatas=metadatas,
        ids=ids
    )
    print(f"Inserted {i + len(batch)} / {len(chunks)} chunks...")

print("✅ Ingestion complete.")
