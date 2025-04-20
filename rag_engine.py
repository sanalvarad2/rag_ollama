import hashlib
from langgraph_engine_with_tools import LangGraphEngine

class RagEngine:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RagEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):  # Asegura que __init__ solo se ejecute una vez
            self._initialized = True
            self.langgraph = LangGraphEngine()
            

    


    def consultar_documentos(self, pregunta: str, collection_name: str, chatId: str):

        resultado = self.langgraph.getLangGraph().invoke({"question": pregunta})

        return resultado

    # def ya_indexado(self, hash_archivo: str, collection_name: str) -> bool:
    #     client = QdrantClient(url=os.getenv("QDRANT_URL"))    

    #     if not client.collection_exists(collection_name=collection_name):
    #         return False

    #     results = client.scroll(
    #         collection_name=collection_name,
    #         scroll_filter={
    #             "must": [
    #                 {"key": "metadata.hash", "match": {"value": hash_archivo}}
    #             ]
    #         },
    #         limit=1
    #     )
    #     print(f"Ya existe: {len(results[0]) > 0}")
    #     return len(results[0]) > 0

    def calcular_hash(archivo_bytes: bytes) -> str:
        return hashlib.sha256(archivo_bytes).hexdigest()
