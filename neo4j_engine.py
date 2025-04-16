from langchain_neo4j import Neo4jGraph, Neo4jVector

from pydantic import BaseModel, Field

import asyncio
import getpass
import os
from datetime import datetime
from hashlib import md5
from typing import Dict, List

from langchain_ollama import OllamaEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

token = os.environ["GITHUB_TOKEN"]
endpoint = "https://models.github.ai/inference"
model_name = "openai/gpt-4o"

class Neo4jEngine:
    _instance = None    

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Neo4jEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):  # Asegura que __init__ solo se ejecute una vez
            self._initialized = True
            self.embedding = OpenAIEmbeddings()
            self.graph = Neo4jGraph(refresh_schema=False, 
                url=os.getenv("NEO4J_URI"),
                username=os.getenv("NEO4J_USERNAME"),
                password=os.getenv("NEO4J_PASSWORD"),
            )
            
            self.initialize_database()

    def initialize_database(self):
        self.graph.query("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE")
        self.graph.query("CREATE CONSTRAINT IF NOT EXISTS FOR (c:AtomicFact) REQUIRE c.id IS UNIQUE")
        self.graph.query("CREATE CONSTRAINT IF NOT EXISTS FOR (c:KeyElement) REQUIRE c.id IS UNIQUE")     

    # neo4j_vector = Neo4jVector.from_existing_graph(
    # url=os.getenv("NEO4J_URI"),
    # username=os.getenv("NEO4J_USERNAME"),
    # password=os.getenv("NEO4J_PASSWORD"),
    # embedding=embeddings,
    # index_name="keyelements",
    # node_label="KeyElement",
    # text_node_properties=["id"],
    # embedding_node_property="embedding",
    # retrieval_query="RETURN node.id AS text, score, {} AS metadata"
    #)
    def getVector(self):
        """
        This method returns a Neo4jGraph object with the specified parameters.
        """
        return Neo4jVector.from_existing_graph(
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            embedding=self.embedding,
            index_name="keyelements",
            node_label="KeyElement",
            text_node_properties=["id"],
            embedding_node_property="embedding",
            retrieval_query="RETURN node.id AS text, score, {} AS metadata"
        )

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

    def encode_md5(self, text):
        print(f"Encoding text: {text}")
        if not isinstance(text, str):
            raise ValueError("Input must be a string")
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
        
    def get_atomic_facts(self, key_elements: List[str]) -> List[Dict[str, str]]:
        data = self.graph.query("""
        MATCH (k:KeyElement)<-[:HAS_KEY_ELEMENT]-(fact)<-[:HAS_ATOMIC_FACT]-(chunk)
        WHERE k.id IN $key_elements
        RETURN distinct chunk.id AS chunk_id, fact.text AS text
        """, params={"key_elements": key_elements})
        return data

    def get_neighbors_by_key_element(self, key_elements):
        print(f"Key elements: {key_elements}")
        data = self.graph.query("""
        MATCH (k:KeyElement)<-[:HAS_KEY_ELEMENT]-()-[:HAS_KEY_ELEMENT]->(neighbor)
        WHERE k.id IN $key_elements AND NOT neighbor.id IN $key_elements
        WITH neighbor, count(*) AS count
        ORDER BY count DESC LIMIT 50
        RETURN collect(neighbor.id) AS possible_candidates
        """, params={"key_elements":key_elements})
        return data
    

    def get_subsequent_chunk_id(self, chunk):
        data = self.graph.query("""
        MATCH (c:Chunk)-[:NEXT]->(next)
        WHERE c.id = $id
        RETURN next.id AS next
        """)
        return data

    def get_previous_chunk_id(self, chunk):
        data = self.graph.query("""
        MATCH (c:Chunk)<-[:NEXT]-(previous)
        WHERE c.id = $id
        RETURN previous.id AS previous
        """)
        return data

    def get_chunk(self, chunk_id: str) -> List[Dict[str, str]]:
        data = self.graph.query("""
        MATCH (c:Chunk)
        WHERE c.id = $chunk_id
        RETURN c.id AS chunk_id, c.text AS text
        """, params={"chunk_id": chunk_id})
        return data



class AtomicFact(BaseModel):
    key_elements: List[str] = Field(description="""The essential nouns (e.g., characters, times, events, places, numbers), verbs (e.g.,
actions), and adjectives (e.g., states, feelings) that are pivotal to the atomic fact's narrative.""")
    atomic_fact: str = Field(description="""The smallest, indivisible facts, presented as concise sentences. These include
propositions, theories, existences, concepts, and implicit elements like logic, causality, event
sequences, interpersonal relationships, timelines, etc.""")

class Extraction(BaseModel):
    atomic_facts: List[AtomicFact] = Field(description="List of atomic facts")