from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from rag_engine import procesar_documento, consultar_documentos, calcular_hash, ya_indexado
import uuid
import os
from dotenv import load_dotenv
load_dotenv() 



app = FastAPI(title="RAG API con Ollama")
collection_name = "docs_rag"
# collection_name = f"user_{user_id}_docs"

@app.post("/cargar-documento/")
async def cargar_documento(file: UploadFile = File(...)):
    extension = os.path.splitext(file.filename)[-1].lower()
    contenido = await file.read()
    hash_archivo = calcular_hash(contenido)
    print(f"Hash del archivo: {hash_archivo}")
    if ya_indexado(hash_archivo, collection_name):
        return {"mensaje": "Este archivo ya fue indexado"}

    os.makedirs("./docs_storage", exist_ok=True)
    path_local = os.path.join("docs_storage", file.filename)

    with open(path_local, "wb") as f:
        f.write(contenido)

    
    resultado = procesar_documento(path_local, collection_name, extension, hash_archivo)
    return {"mensaje": resultado}

@app.get("/chat-id/")
def get_chat_id():
    return str(uuid.uuid4())

@app.post("/preguntar/")
async def preguntar_a_documentos(pregunta: str = Form(...), chatId: str = Form(None)):
    
    if chatId is None:
        chatId = get_chat_id()

    respuesta, fuentes = consultar_documentos(pregunta, collection_name)
    return JSONResponse(content={
        "respuesta": respuesta,
        "fuentes": fuentes,
        "chatId": chatId
    })