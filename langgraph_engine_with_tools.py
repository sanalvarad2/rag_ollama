from langgraph.graph import StateGraph, START, END
from langGraph_state import InputState, OutputState, OverallState
from chains_with_tools import Chains
from neo4j_engine import Neo4jEngine
from typing import List, Literal


import re
import ast

from  uuid import UUID
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langchain_core.messages import ToolMessage

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.prebuilt import ToolNode

from typing_extensions import Any, Annotated


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
            
    def InicializarLangGraph(self):
        langgraph = StateGraph(OverallState, input=InputState, output=OutputState)
        langgraph.add_node(self.rational_plan_node)
        langgraph.add_node(self.initial_node_selection)
        langgraph.add_node(self.atomic_fact_check)
        langgraph.add_node(self.chunk_check)
        langgraph.add_node(self.answer_reasoning)
        langgraph.add_node(self.neighbor_select)
        langgraph.add_node("tools", self.tool_node)
        langgraph.add_edge(START, "rational_plan_node")
        langgraph.add_edge("rational_plan_node", "initial_node_selection")
        langgraph.add_edge("initial_node_selection", "atomic_fact_check")
        langgraph.add_edge("tools", "atomic_fact_check")
        langgraph.add_conditional_edges(
            "atomic_fact_check",
            self.should_continue,
        )
        langgraph.add_conditional_edges(
            "chunk_check",
            self.chunk_condition,
        )
        langgraph.add_conditional_edges(
            "neighbor_select",
            self.neighbor_condition,
        )
        langgraph.add_edge("answer_reasoning", END)

        langgraph = langgraph.compile()
        return langgraph
    
    def getLangGraph(self):
        return self.langgraph
    
    def parse_function(self, input_str):
    # Regular expression to capture the function name and arguments
        pattern = r'(\w+)(?:\((.*)\))?'
    
        match = re.match(pattern, input_str)
        if match:
            function_name = match.group(1)  # Extract the function name
            raw_arguments = match.group(2)  # Extract the arguments as a string        
            # If there are arguments, attempt to parse them
            arguments = []
            if raw_arguments:
                try:
                    # Use ast.literal_eval to safely evaluate and convert the arguments
                    parsed_args = ast.literal_eval(f'({raw_arguments})')  # Wrap in tuple parentheses
                    # Ensure it's always treated as a tuple even with a single argument
                    arguments = list(parsed_args) if isinstance(parsed_args, tuple) else [parsed_args]
                except (ValueError, SyntaxError):
                    # In case of failure to parse, return the raw argument string
                    arguments = [raw_arguments.strip()]


            return {
                'function_name': function_name,
                'arguments': arguments
            }
        else:
            return None



    def rational_plan_node(self, state: InputState) -> OverallState:
        rational_plan = self.chains.getRationalChain().invoke({"question": state.get("question"), "messages": HumanMessage(content=state.get("question"))})
        print("-" * 20)
        print(f"Step: rational_plan")
        print(f"Rational plan: {rational_plan}")
        return {
            "rational_plan": rational_plan,
            "previous_actions": ["rational_plan"],
            "messages": [AIMessage(content=rational_plan)]
        }
    
    def get_potential_nodes(self, question: str) -> List[str]:
        data = self.neo4j_graph.getVector().similarity_search(question, k=50)
        return [el.page_content for el in data]
    
    def initial_node_selection(self, state: OverallState) -> OverallState:
        potential_nodes = self.get_potential_nodes(state.get("question"))
        initial_nodes = self.chains.getInitialNodeChain().invoke(
            {
                "question": state.get("question"),
                "rational_plan": state.get("rational_plan"),
                "nodes": potential_nodes,
            }
        )
        print(f"response: {initial_nodes.get("parsed").initial_nodes}")
        # paper uses 5 initial nodes
        check_atomic_facts_queue = [
            el.key_element
            for el in sorted(
                initial_nodes.get("parsed").initial_nodes,
                key=lambda node: node.score,
                reverse=True,
            )
        ][:5]
        return {
            "check_atomic_facts_queue": check_atomic_facts_queue,
            "previous_actions": ["initial_node_selection"],
            "messages": [initial_nodes.get("raw")]
        }
    
    def atomic_fact_check(self, state: OverallState) -> OverallState:
        atomic_facts = self.neo4j_graph.get_atomic_facts(state.get("check_atomic_facts_queue"))
        print("-" * 20)
        print(f"Step: atomic_fact_check")
        print(
            f"Reading atomic facts about: {state.get('check_atomic_facts_queue')}"
        )
        atomic_facts_results = self.chains.getAtomicFactChain([self.stop_and_read_neighbor, self.read_chunk]).invoke(
            {
                "question": state.get("question"),
                "rational_plan": state.get("rational_plan"),
                "notebook": state.get("notebook"),
                "previous_actions": state.get("previous_actions"),
                "atomic_facts": atomic_facts,
            }
        )
        print(f"raw response: {atomic_facts_results}")

        notebook = state.get("notebook"),
        if not atomic_facts_results.tool_calls:
            notebook = atomic_facts_results.content
        response = {
            "notebook": notebook,
            #"chosen_action": chosen_action.get("function_name"),
            "check_atomic_facts_queue": [],
            "previous_actions": [
                f"atomic_fact_check({state.get('check_atomic_facts_queue')})"
            ],
            "messages": [atomic_facts_results]
        }
        
        return response
    

    def chunk_check(self, state: OverallState) -> OverallState:
        check_chunks_queue = state.get("check_chunks_queue")
        print(f"Check chunks queue: {check_chunks_queue}")
        if not check_chunks_queue:
            return {
                "chosen_action": "termination",
                "previous_actions": ["chunk_check"],
            }
        chunk_id = check_chunks_queue.pop()
        print("-" * 20)
        print(f"Step: read chunk({chunk_id})")

        chunks_text = self.neo4j_graph.get_chunk(chunk_id)
        read_chunk_results = self.chains.getChunkReadChain().invoke(
            {
                "question": state.get("question"),
                "rational_plan": state.get("rational_plan"),
                "notebook": state.get("notebook"),
                "previous_actions": state.get("previous_actions"),
                "chunk": chunks_text,
            }
        )

        notebook = read_chunk_results.updated_notebook
        print(
            f"Rational for next action after reading chunks: {read_chunk_results.rational_next_move}"
        )
        chosen_action = self.parse_function(read_chunk_results.chosen_action)
        print(f"Chosen action: {chosen_action}")
        response = {
            "notebook": notebook,
            "chosen_action": chosen_action.get("function_name"),
            "previous_actions": [f"read_chunks({chunk_id})"],
        }
        if chosen_action.get("function_name") == "read_subsequent_chunk":
            subsequent_id = self.neo4j_graph.get_subsequent_chunk_id(chunk_id)
            check_chunks_queue.append(subsequent_id)
        elif chosen_action.get("function_name") == "read_previous_chunk":
            previous_id = self.neo4j_graph.get_previous_chunk_id(chunk_id)
            check_chunks_queue.append(previous_id)
        elif chosen_action.get("function_name") == "search_more":
            # Go over to next chunk
            # Else explore neighbors
            if not check_chunks_queue:
                response["chosen_action"] = "search_neighbor"
                # Get neighbors/use vector similarity
                print(f"Neighbor rational: {read_chunk_results.rational_next_move}")
                neighbors = self.get_potential_nodes(
                    read_chunk_results.rational_next_move
                )
                response["neighbor_check_queue"] = neighbors

        response["check_chunks_queue"] = check_chunks_queue
        return response
    
    def neighbor_select(self, state: OverallState) -> OverallState:
        print("-" * 20)
        print(f"Step: neighbor select")
        print(f"Possible candidates: {state.get('neighbor_check_queue')}")
        neighbor_select_results = self.chains.getNeighborSelectChain().invoke(
            {
                "question": state.get("question"),
                "rational_plan": state.get("rational_plan"),
                "notebook": state.get("notebook"),
                "nodes": state.get("neighbor_check_queue"),
                "previous_actions": state.get("previous_actions"),
            }
        )
        print(
            f"Rational for next action after selecting neighbor: {neighbor_select_results.rational_next_move}"
        )
        chosen_action = self.parse_function(neighbor_select_results.chosen_action)
        print(f"Chosen action: {chosen_action}")
        # Empty neighbor select queue
        response = {
            "chosen_action": chosen_action.get("function_name"),
            "neighbor_check_queue": [],
            "previous_actions": [
                f"neighbor_select({chosen_action.get('arguments', [''])[0] if chosen_action.get('arguments', ['']) else ''})"
            ],
        }
        if chosen_action.get("function_name") == "read_neighbor_node":
            response["check_atomic_facts_queue"] = [
                chosen_action.get("arguments")[0]
            ]
        return response
    
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
    
    def atomic_fact_condition(
            self,
            state: OverallState,
        ) -> Literal["neighbor_select", "chunk_check"]:
        if state.get("chosen_action") == "stop_and_read_neighbor":
            return "neighbor_select"
        elif state.get("chosen_action") == "read_chunk":
            return "chunk_check"

    def chunk_condition(
            self,
            state: OverallState,
        ) -> Literal["answer_reasoning", "chunk_check", "neighbor_select"]:
        if state.get("chosen_action") == "termination":
            return "answer_reasoning"
        elif state.get("chosen_action") in ["read_subsequent_chunk", "read_previous_chunk", "search_more"]:
            return "chunk_check"
        elif state.get("chosen_action") == "search_neighbor":
            return "neighbor_select"

    def neighbor_condition(
            self,
            state: OverallState,
        ) -> Literal["answer_reasoning", "atomic_fact_check"]:
        if state.get("chosen_action") == "termination":
            return "answer_reasoning"
        elif state.get("chosen_action") == "read_neighbor_node":
            return "atomic_fact_check"

    def should_continue(self, state: OverallState):
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        
        

    def tool_node(self, state: OverallState) -> OverallState:
        # This method is used to call the tool node in the graph
        # It will be called by the graph engine when needed
        tools = [self.stop_and_read_neighbor, self.read_chunk]
        return ToolNode(
            tools=tools,
        )

    @tool
    def stop_and_read_neighbor(key_elements: List[str], tool_call_id: Annotated[str, InjectedToolCallId], config: RunnableConfig) -> List[str]:
        """
        Use this tool to find and read the neighbors of the key elements.
        """


        print(f"Key elements: {key_elements}")
        neighbors = Neo4jEngine().get_neighbors_by_key_element(key_elements)
        return Command(
            update={
            # update the state keys
            "neighbor_check_queue": neighbors,
            # update the message history
            "messages": [
                ToolMessage(
                    "Successfully looked for neighbors elements", tool_call_id=tool_call_id
                )
            ],
            },
            goto="neighbor_select",
        )
         
    @tool
    def read_chunk(chunks:List[str], tool_call_id: Annotated[str, InjectedToolCallId], config: RunnableConfig):
        """
        Use this tool to read a chunk of text.
        """
        print(f"Chunk: {chunks}")
        
        return Command(
            update={
            # update the state keys
            "check_chunks_queue": chunks,
            # update the message history
            "messages": [
                ToolMessage(
                    "Successfully load chunk to read", tool_call_id=tool_call_id
                )
            ],
            },
            goto="chunk_check"
        )
       