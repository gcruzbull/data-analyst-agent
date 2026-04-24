
import sys
print("PYTHON:", sys.executable)

from src.tools.retriever import retrieve
from langchain_ollama import OllamaEmbeddings

query = "ventas en UK con mayor cantidad"

docs = retrieve(query)

print("Docs encontrados:", len(docs))  # 👈 AGREGA ESTO

for doc in docs:
    print(doc.page_content)
    print("-----")
    
emb = OllamaEmbeddings(
    model="llama3",
    base_url="http://localhost:11434"
)

print(emb.embed_query("ventas en UK"))