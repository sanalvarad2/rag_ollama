from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.language_models.chat_models import BaseChatModel

from langchain_core.tools import Tool

from prompts_with_tools import (
    rational_prompt,
    initial_node_prompt,
    answer_reasoning_prompt,
    atomic_fact_check_prompt,
    chunk_read_prompt,
    neighbor_select_prompt
)

from langGraph_state import (InputState, OutputState, OverallState,
                            InitialNodes, AtomicFactOutput, ChunkOutput,
                            NeighborOutput, AnswerReasonOutput)

import os


token = os.getenv("GITHUB_TOKEN")
# endpoint = "https://models.github.ai/inference"
endpoint = "http://localhost:11434/v1/"

model_name = "llama3.1:8b"
api_version = "2025-01-01-preview"

class Chains:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Chains, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):  # Asegura que __init__ solo se ejecute una vez
            self._initialized = True
            self.embedding = OllamaEmbeddings(model="nomic-embed-text:latest", base_url=os.getenv("OLLAMA_URL"))
            self.llm = ChatOpenAI(
                                    # or your api version
                                    model=model_name,
                                    base_url=endpoint,
                                    api_key=token,
                                    # or your endpoint
                                )

    def getRationalChain(self, tools: list[Tool]= []):
        """
        This method returns the rational chain, which is a combination of the rational prompt,
        the language model (LLM), and the string output parser.
        """
        # Define the rational chain using the rational prompt, LLM, and string output parser
        
        rational_chain = rational_prompt | self.llm | StrOutputParser()
        return rational_chain
    
    def getAtomicFactChain(self, tools: list[Tool]= []):
        """
        This method returns the atomic fact chain, which is a combination of the atomic fact check prompt,
        the language model (LLM), and the string output parser.
        """
        # Define the atomic fact chain using the atomic fact check prompt, LLM, and string output parser
        llm_with_tools:BaseChatModel = self.llm.bind_tools([*tools])
        atomic_fact_chain = atomic_fact_check_prompt | llm_with_tools
        return atomic_fact_chain
    

    def getInitialNodeChain(self, tools: list[Tool]= []):
        """
        This method returns the initial node chain, which is a combination of the initial node prompt,
        the language model (LLM), and the string output parser.
        """
        # Define the initial node chain using the initial node prompt, LLM, and string output parser
        llm_with_tools:BaseChatModel = self.llm.bind_tools(tools)
        initial_nodes_chain = initial_node_prompt | llm_with_tools.with_structured_output(InitialNodes, include_raw=True)
        return initial_nodes_chain
    
    def getChunkReadChain(self, tools: list[Tool]= []):
        """
        This method returns the chunk read chain, which is a combination of the chunk read prompt,
        the language model (LLM), and the string output parser.
        """
        # Define the chunk read chain using the chunk read prompt, LLM, and string output parser
        llm_with_tools:BaseChatModel = self.llm.bind_tools(tools)
        chunk_read_chain = chunk_read_prompt | llm_with_tools.with_structured_output(ChunkOutput)
        return chunk_read_chain
    
    #neighbor_select_chain = neighbor_select_prompt | llm.with_structured_output(NeighborOutput)
    def getNeighborSelectChain(self, tools: list[Tool]= []):
        """
        This method returns the neighbor select chain, which is a combination of the neighbor select prompt,
        the language model (LLM), and the string output parser.
        """
        # Define the neighbor select chain using the neighbor select prompt, LLM, and string output parser
        llm_with_tools:BaseChatModel = self.llm.bind_tools(tools)
        neighbor_select_chain = neighbor_select_prompt | llm_with_tools.with_structured_output(NeighborOutput)
        return neighbor_select_chain
    
    #answer_reasoning_chain = answer_reasoning_prompt | llm.with_structured_output(AnswerReasonOutput)
    def getAnswerReasoningChain(self, tools: list[Tool]= []):
        """
        This method returns the answer reasoning chain, which is a combination of the answer reasoning prompt,
        the language model (LLM), and the string output parser.
        """
        # Define the answer reasoning chain using the answer reasoning prompt, LLM, and string output parser
        llm_with_tools:BaseChatModel = self.llm.bind_tools(tools)
        answer_reasoning_chain = answer_reasoning_prompt | llm_with_tools.with_structured_output(AnswerReasonOutput)
        return answer_reasoning_chain