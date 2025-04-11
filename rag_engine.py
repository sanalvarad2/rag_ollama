from langchain_community.document_loaders import PyPDFLoader, BSHTMLLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
import hashlib

import os

def procesar_documento(path_archivo: str, collection_name: str, extension: str, hash_archivo: str):
    # 1. Loader para PDF o HTML
    if extension == ".pdf":
        loader = PyPDFLoader(path_archivo)
    elif extension == ".html":
        loader = BSHTMLLoader(path_archivo)
    else:
        return "Formato no soportado. Usa PDF o HTML."

    documentos = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = splitter.split_documents(documentos)

    for doc in chunks:
        doc.metadata["hash"] = hash_archivo

    embeddings = OllamaEmbeddings(model=os.getenv("MODEL_EMBEDDING"), base_url=os.getenv("OLLAMA_URL"))

    # 2. Conectar con Qdrant (local o remoto)
    qdrant = QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        location=os.getenv("QDRANT_URL"),  # Cambia si estás en cloud
        collection_name=collection_name,
    )

    return f"Documento cargado en la colección '{collection_name}' de Qdrant."

def consultar_documentos(pregunta: str, collection_name: str):
    
    embeddings = OllamaEmbeddings(model=os.getenv("MODEL_EMBEDDING"), base_url=os.getenv("OLLAMA_URL"))

    client = QdrantClient(url=os.getenv("QDRANT_URL"))

    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings
    )

    llm = ChatOllama(model=os.getenv("MODEL"), base_url=os.getenv("OLLAMA_URL"))

    prompt_template = """
    Usa los siguientes documentos para responder de forma clara y precisa.
    Si no encuentras la respuesta en los documentos, solo informalo.
    No inventes información.
    No incluyas información irrelevante ni detalles innecesarios.

    Documentos:
    ```
    {context}
    ```
    Pregunta:
    {question}
    """

    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])

    print(f"Prompt usado: {prompt_template}")
 

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5}),
        chain_type="stuff",
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )

    resultado = qa_chain.invoke(pregunta)
    fuentes = [[doc.metadata.get("source", "desconocido"), doc.metadata.get("page_label", "desconocido")] for doc in resultado["source_documents"]]
    return resultado["result"], fuentes

def ya_indexado(hash_archivo: str, collection_name: str) -> bool:
    client = QdrantClient(url=os.getenv("QDRANT_URL"))
    results = client.scroll(
        collection_name=collection_name,
        scroll_filter={
            "must": [
                {"key": "metadata.hash", "match": {"value": hash_archivo}}
            ]
        },
        limit=1
    )
    print(f"Ya existe: {len(results[0]) > 0}")
    return len(results[0]) > 0

def calcular_hash(archivo_bytes: bytes) -> str:
    return hashlib.sha256(archivo_bytes).hexdigest()
