from langgraph.graph import StateGraph, START, END
from langGraph_state import InputState, OutputState, OverallState
from chains_with_tools import Chains
from neo4j_engine import Neo4jEngine
from typing import List, Literal, Dict


import re
import ast

from  uuid import UUID
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langchain_core.messages import ToolMessage

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.prebuilt import ToolNode, InjectedState

from typing_extensions import Any, Annotated, Optional


class LangGraphEngine:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(LangGraphEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):  # Asegura que __init__ solo se ejecute una vez
            self._initialized = True
            self.chains = Chains()
            self.neo4j_graph = Neo4jEngine()
            self.langgraph = self.InicializarLangGraph()
            self.tools = self.getTools()

    def getTools(self):
        """
        This method returns a list of tools that can be used in the langgraph.
        """
        return [
                    self.get_initial_nodes,
                    self.get_neighbor,
                    self.read_chunk,
                    self.get_subsequent_chunk,
                    self.get_previous_chunk,
                    self.search_more_nodes,
                    self.termination
                ]
            
    def InicializarLangGraph(self):
        langgraph = StateGraph(OverallState, input=InputState, output=OutputState)
        langgraph.add_node(self.rational_plan_node)
        langgraph.add_node(self.retrival_node)
        langgraph.add_node(self.answer_reasoning)
        langgraph.add_node("tools", self.tool_node)

        langgraph.add_edge(START, "rational_plan_node")
        langgraph.add_edge("rational_plan_node", "node_retrival")

        langgraph.add_edge("tools", "retrival_node")

        langgraph.add_conditional_edges(
            "retrival_node",
            self.should_continue,
        )

        langgraph.add_edge("answer_reasoning", END)

        langgraph = langgraph.compile()
        return langgraph
    
    def getLangGraph(self):
        return self.langgraph
    
    def rational_plan_node(self, state: InputState) -> OverallState:
        rational_plan = self.chains.getRationalChain().invoke({"question": state.get("question")})
        print("-" * 20)
        print(f"Step: rational_plan")
        
        return {
            "messages": [rational_plan]
        }

    def retrival_node(self, state: OverallState) -> OverallState:
        # This method is used to call the node retrival in the graph
        # It will be called by the graph engine when needed
        print("-" * 20)
        print(f"Step: node_retrival")
        print(f"Question: {state.get('question')}")

        #get messages from the state
        messages = state.get("messages")
        node_retrival = self.chains.getNodeRetrivalChain(self.tools).invoke(messages)
        
        return {
            "messages": [node_retrival],
        }
    
    def answer_reasoning(self, state: OverallState) -> OutputState:
        print("-" * 20)
        print("Step: Answer Reasoning")
        final_answer = self.chains.getAnswerReasoningChain().invoke(
            {"question": state.get("question"), "notebook": state.get("notebook")}
        )
        return {
            "answer": final_answer.final_answer,
            "analysis": final_answer.analyze,
            "previous_actions": ["answer_reasoning"],
        }

    def should_continue(self, state: OverallState):
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        
        

    def tool_node(self, state: OverallState) -> ToolNode:
        # This method is used to call the tool node in the graph
        # It will be called by the graph engine when needed
        
        return ToolNode(
            tools=self.tools,
        )
    
    @tool
    def get_initial_nodes(question: str, tool_call_id: Annotated[str, InjectedToolCallId]):
        """
        Use this tool to get the initial nodes for the question.
        this will be used to get the initial nodes for the question at the beginning of the execution.
        """
        print(f"Question: {question}")
        data = [el.page_content for el in Neo4jEngine.getVector().similarity_search(question, k=50)]
        return data
    


    @tool
    def get_neighbor(key_elements: List[str], tool_call_id: Annotated[str, InjectedToolCallId]) -> List[Dict[str, Any]]:
        """
        Use this tool to find and get the neighbors of the key elements.
        this will return a list of dictionaries with the key elements and their neighbors.
        Example: get_neighbor(['c9e314c10d8b517e92d492aa0d584500', 'f8b8c4d0d8b517e92d492aagr34500'])
        -> ['asdfhj352935234cdgssdasd12334 ', 'f8b892aa0d5842d492aagr34500']},
        """


        print(f"Key elements: {key_elements}")
        neighbors = Neo4jEngine().get_neighbors_by_key_element(key_elements)
        return neighbors
         
    @tool
    def read_chunk(chunk_id:str, tool_call_id: Annotated[str, InjectedToolCallId]) -> List[Dict[str, str]]:
        """
        Use this tool to read a chunk of text.
        Example: read_chunk('c9e314c10d8b517e92d492aa0d584500') -> [{{'chunk_id':'c9e314c10d8b517e92d492aa0d584500', 'text':'this is a chunk of text'}}]
        """
        # print(f"Chunk: {chunks}")

        chunk = Neo4jEngine().get_chunk(chunk_id)
        
        return chunk
    
    @tool
    def get_subsequent_chunk(chunk_id: str, tool_call_id: Annotated[str, InjectedToolCallId], state: Annotated[OverallState, InjectedState]) -> List[Dict[str, str]]:
        """
        Use this tool to get a subsequent chunk of text from a given chunk id.
        Example: get_subsequent_chunk('c9e314c10d8b517e92d492aa0d584500') -> ['f8b8c4d0d8b517e92d492aagr34500']
        """
        print(f"Chunk: {chunk_id}")

        subsequent_id = Neo4jEngine().get_subsequent_chunk_id(chunk_id)
        return subsequent_id
    
    @tool
    def get_previous_chunk(chunk_id: str, tool_call_id: Annotated[str, InjectedToolCallId], state: Annotated[OverallState, InjectedState]):
        """
        Use this tool to get a previous chunk of text from a given chunk id.
        Example: get_previous_chunk('c9e314c10d8b517e92d492aa0d584500') -> ['f8b8c4d0d8b517e92d492aagr34500']
        """
        print(f"Chunk: {chunk_id}")

        # previous_id = self.neo4j_graph.get_previous_chunk_id(chunk_id)
        #     check_chunks_queue.append(previous_id)

        previous_id = Neo4jEngine().get_previous_chunk_id(chunk_id)
        return previous_id
    
    @tool
    def search_more_nodes(input_to_seach: str, tool_call_id: Annotated[str, InjectedToolCallId], state: Annotated[OverallState, InjectedState]):
        """
        Use this tools to get more nodes from the database based on the input when the nodes previously getted are not enough for provide and answer.
        Example: search_more_nodes('Formula') -> ['f8b8c4d0d8b517e92d492aagr34500', 'fd492aagr348b517e92d492aagr34500']
        """
        print(f"Input to search: {input_to_seach}")
        data = Neo4jEngine().getVector().similarity_search(input_to_seach, k=50)
        neighbors = [el.page_content for el in data]
        return neighbors
    
    @tool
    def termination(context: str, tool_call_id: Annotated[str, InjectedToolCallId]):
        """
        Use this tool when you have enough information to get a response.
        """
        return Command(
            update={
                # update the state keys
                "notebook": context,
                # update the message history
                "messages": [
                    ToolMessage(
                        "Successfully terminated the process", tool_call_id=tool_call_id
                    )
                ],
            },
            goto="answer_reasoning"
        )