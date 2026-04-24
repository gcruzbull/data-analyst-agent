from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

from src.tools.data_loader import load_data

vectorstore = None

def build_vectorstore():
    df = load_data().head(50)  # Limitar a las primeras 500 filas para pruebas

    documents = []
    
    print("📦 Construyendo documentos...")

    for i, (_, row) in enumerate(df.iterrows()):
        content = f"""
        Invoice: {row['InvoiceNo']}
        Product: {row['Description']}
        Quantity: {row['Quantity']}
        Price: {row['UnitPrice']}
        Country: {row['Country']}
        """

        documents.append(Document(page_content=content))
        
        if i % 50 == 0:
            print(f"Procesadas {i} filas...")
            
    print("🧠 Generando embeddings... (esto puede tardar)")

    embeddings = OllamaEmbeddings(
        model="llama3",
        base_url="http://localhost:11434"
    )

    print("📊 Construyendo FAISS...")
    
    vectorstore = FAISS.from_documents(documents, embeddings)
    
    print("✅ Vectorstore listo")

    return vectorstore

def init_vectorstore():
    global vectorstore
    vectorstore = build_vectorstore()


def retrieve(query: str):
    print("Usando FAISS 🔥")
    return vectorstore.similarity_search(query, k=5)