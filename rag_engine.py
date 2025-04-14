from langchain_community.document_loaders import PyPDFLoader, BSHTMLLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore


from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

import hashlib

from conversation_history import ConversationHistory

import os

prompt_template = """
    Usa los siguientes documentos para responder de forma clara y precisa.
    Si no encuentras la respuesta en los documentos, solo informalo.
    No inventes información.
    No incluyas información irrelevante ni detalles innecesarios.

    Ten en cuenta las conversaciones anteriores para responder mas precisamente.

    Historial:
    ```
    {history}
    ```

    Documentos:
    ```
    {context}
    ```
    Pregunta:
    {question}
    """

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

def formatear_fuentes(fuentes):
    return "\n\n".join(doc.page_content for doc in fuentes)

def consultar_documentos(pregunta: str, collection_name: str, chatId: str):
    conversation_history = ConversationHistory()

    history_chat = conversation_history.get_last_10_conversations(chatId)
    history = ""
    for user_message, ai_response in history_chat:
        history += f"User: {user_message}\n"
        history += f"Assistant: {ai_response}\n"

    print(f"Historial de la conversación: {history}")

    embeddings = OllamaEmbeddings(model=os.getenv("MODEL_EMBEDDING"), base_url=os.getenv("OLLAMA_URL"))

    client = QdrantClient(url=os.getenv("QDRANT_URL"))

    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings
    )

    llm = ChatOllama(model=os.getenv("MODEL"), base_url=os.getenv("OLLAMA_URL"))

 

    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question", "history"], partial_variables={"history": history})


    print(f"Prompt usado: {prompt}")
 

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5}),
        chain_type="stuff",
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )

    
    # qa_chain = (
    #     {
    #         "history": history,
    #         "context": vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5}) | formatear_fuentes,
    #         "question": RunnablePassthrough(),
    #     }
    #     | prompt_template
    #     | llm
    #     | StrOutputParser()
    # )

    resultado = qa_chain.invoke(pregunta)
    fuentes = [[doc.metadata.get("source", "desconocido"), doc.metadata.get("page_label", "desconocido")] for doc in resultado["source_documents"]]

    conversation_history.add_conversation(chatId, pregunta, resultado["result"])

    return resultado["result"], fuentes

def ya_indexado(hash_archivo: str, collection_name: str) -> bool:
    client = QdrantClient(url=os.getenv("QDRANT_URL"))    

    if not client.collection_exists(collection_name=collection_name):
        return False
    
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
