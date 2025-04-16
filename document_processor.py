from langchain_community.document_loaders import PyPDFLoader, BSHTMLLoader
from langchain.text_splitter import TokenTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from neo4j_engine import Neo4jEngine, Extraction

import asyncio
import getpass
import os
from datetime import datetime
from hashlib import md5
from typing import Dict, List

# import pandas as pd
# import seaborn as sns
import tiktoken

from langchain_neo4j import Neo4jGraph
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_text_splitters import TokenTextSplitter
from pydantic import BaseModel, Field

from langchain_openai import AzureChatOpenAI
from langchain_ollama import ChatOllama

class DocumentProcessor:
    _instance = None

    construction_system = """
    You are now an intelligent assistant tasked with meticulously extracting both key elements and
    atomic facts from a long text.
    1. Key Elements: The essential nouns (e.g., characters, times, events, places, numbers), verbs (e.g.,
    actions), and adjectives (e.g., states, feelings) that are pivotal to the text’s narrative.
    2. Atomic Facts: The smallest, indivisible facts, presented as concise sentences. These include
    propositions, theories, existences, concepts, and implicit elements like logic, causality, event
    sequences, interpersonal relationships, timelines, etc.
    Requirements:
    #####
    1. Ensure that all identified key elements are reflected within the corresponding atomic facts.
    2. You should extract key elements and atomic facts comprehensively, especially those that are
    important and potentially query-worthy and do not leave out details.
    3. Whenever applicable, replace pronouns with their specific noun counterparts (e.g., change I, He,
    She to actual names).
    4. Ensure that the key elements and atomic facts you extract are presented in the same language as
    the original text (e.g., English or Chinese).
    """

    construction_human = """Use the given format to extract information from the 
    following input: {input}"""

    construction_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                construction_system,
            ),
            (
                "human",
                (
                    "Use the given format to extract information from the "
                    "following input: {input}"
                ),
            ),
        ]
    )

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DocumentProcessor, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):  # Asegura que __init__ solo se ejecute una vez
            self._initialized = True
            self.neo4j = Neo4jEngine()
            self.model = ChatOllama(model="llama3.2:3b", temperature=0.1, base_url="http://localhost:11434")   
            self.structured_llm = self.model.with_structured_output(Extraction)
            self.extraction_chain = self.construction_prompt | self.structured_llm
            self.splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
            # self.checkAzure()

    def checkAzure(self):
        res = self.model.invoke("Hello, how can I assist you today?")
        print(f"Respuesta: {res}")

    async def procesar_documento(self, path_archivo: str, collection_name: str, extension: str, hash_archivo: str):
        start = datetime.now()
        print(f"Iniciada el procesamiento: {start}")

        # 1. Loader para PDF o HTML
        if extension == ".pdf":
            loader = PyPDFLoader(path_archivo)
        elif extension == ".html":
            loader = BSHTMLLoader(path_archivo)
        else:
            return "Formato no soportado. Usa PDF o HTML."

        documentos = loader.load()
        print(f"Nombre del documento: {documentos[0].metadata.get("source", "desconocido")}")
        nombre_documento = documentos[0].metadata.get("source", "desconocido")


        chunks = self.splitter.split_documents(documentos)
        print(f"Total text chunks: {len(chunks)}")


        # 2. Procesar cada chunk
        tasks = [
            asyncio.create_task(self.extraction_chain.ainvoke({"input":chunk_text.page_content}))
            for index, chunk_text in enumerate(chunks)
        ]

        results = await asyncio.gather(*tasks)
        print(f"Finalizado extraccion via LLM despues de: {datetime.now() - start}")

        docs = [el.dict() for el in results]
        for index, doc in enumerate(docs):
            # print(f"Chunk {index}: {chunks[index]}")
            page_content = chunks[index].page_content
            # print(f"Page {index}: {page_content}")
            doc['chunk_id'] = self.neo4j.encode_md5(page_content)
            doc['chunk_text'] = page_content
            doc['index'] = index
            for af in doc["atomic_facts"]:
                af["id"] = self.neo4j.encode_md5(af["atomic_fact"])

        self.neo4j.insert_data(docs, nombre_documento)

        self.neo4j.create_relationship(nombre_documento)


        print(f"Finished import at: {datetime.now() - start}")
        return "Documento procesado y almacenado exitosamente."
       
        
    

