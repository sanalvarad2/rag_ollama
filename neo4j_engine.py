from langchain_community.graphs import Neo4jGraph

from pydantic import BaseModel, Field

import asyncio
import getpass
import os
from datetime import datetime
from hashlib import md5
from typing import Dict, List

class Neo4jEngine:
    _instance = None    

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Neo4jEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):  # Asegura que __init__ solo se ejecute una vez
            self._initialized = True
            self.graph = Neo4jGraph(refresh_schema=False)
            self.initialize_database()

    def initialize_database(self):
        self.graph.query("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE")
        self.graph.query("CREATE CONSTRAINT IF NOT EXISTS FOR (c:AtomicFact) REQUIRE c.id IS UNIQUE")
        self.graph.query("CREATE CONSTRAINT IF NOT EXISTS FOR (c:KeyElement) REQUIRE c.id IS UNIQUE")        

    import_query = """
    MERGE (d:Document {id:$document_name})
    WITH d
    UNWIND $data AS row
    MERGE (c:Chunk {id: row.chunk_id})
    SET c.text = row.chunk_text,
        c.index = row.index,
        c.document_name = row.document_name
    MERGE (d)-[:HAS_CHUNK]->(c)
    WITH c, row
    UNWIND row.atomic_facts AS af
    MERGE (a:AtomicFact {id: af.id})
    SET a.text = af.atomic_fact
    MERGE (c)-[:HAS_ATOMIC_FACT]->(a)
    WITH c, a, af
    UNWIND af.key_elements AS ke
    MERGE (k:KeyElement {id: ke})
    MERGE (a)-[:HAS_KEY_ELEMENT]->(k)
    """ 

    def encode_md5(text):
        return md5(text.encode("utf-8")).hexdigest()
    
    def insert_data(self, data: List[Dict], document_name: str):
        self.graph.query(self.import_query, 
            params={"data": data, "document_name": document_name})
        
    def create_relationship(self, document_name: str):
        self.graph.query("""MATCH (c:Chunk)<-[:HAS_CHUNK]-(d:Document)
            WHERE d.id = $document_name
            WITH c ORDER BY c.index WITH collect(c) AS nodes
            UNWIND range(0, size(nodes) -2) AS index
            WITH nodes[index] AS start, nodes[index + 1] AS end
            MERGE (start)-[:NEXT]->(end)
            """,
           params={"document_name":document_name})



class AtomicFact(BaseModel):
    key_elements: List[str] = Field(description="""The essential nouns (e.g., characters, times, events, places, numbers), verbs (e.g.,
actions), and adjectives (e.g., states, feelings) that are pivotal to the atomic fact's narrative.""")
    atomic_fact: str = Field(description="""The smallest, indivisible facts, presented as concise sentences. These include
propositions, theories, existences, concepts, and implicit elements like logic, causality, event
sequences, interpersonal relationships, timelines, etc.""")

class Extraction(BaseModel):
    atomic_facts: List[AtomicFact] = Field(description="List of atomic facts")