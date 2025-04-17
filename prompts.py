from prompt_templates import rational_plan_system, initial_node_system, atomic_fact_check_system, chunk_read_system_prompt, neighbor_select_system_prompt, answer_reasoning_system_prompt

from langchain_core.prompts import ChatPromptTemplate


rational_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            rational_plan_system,
        ),
        (
            "human",
            (
                "{question}"
            ),
        ),
    ]
)

initial_node_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            initial_node_system,
        ),
        (
            "human",
            (
                """Question: {question}
                   Plan: {rational_plan}
                   Nodes: {nodes}
                """
            ),
        ),
    ]
)

answer_reasoning_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            answer_reasoning_system_prompt,
        ),
        (
            "human",
            (
                """Question: {question}
Notebook: {notebook}"""
            ),
        ),
    ]
)

atomic_fact_check_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            atomic_fact_check_system,
        ),
        (
            "human",
            (
                """Question: {question}
Plan: {rational_plan}
Previous actions: {previous_actions}
Notebook: {notebook}
Atomic facts: {atomic_facts}"""
            ),
        ),
    ]
)

chunk_read_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            chunk_read_system_prompt,
        ),
        (
            "human",
            (
                """Question: {question}
                    Plan: {rational_plan}
                    Previous actions: {previous_actions}
                    Notebook: {notebook}
                    Chunk: {chunk}"""
            ),
        ),
    ]
)

neighbor_select_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            neighbor_select_system_prompt,
        ),
        (
            "human",
            (
                """Question: {question}
Plan: {rational_plan}
Previous actions: {previous_actions}
Notebook: {notebook}
Neighbor nodes: {nodes}"""
            ),
        ),
    ]
)
