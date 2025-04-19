from langchain_core.tools import tool

from langgraph.prebuilt import ToolNode

from typing import Literal

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END


from langchain_core.messages import AIMessage

from IPython.display import Image, display


ollama_endpoint = "http://localhost:11434/v1/"
model = "llama3.2:3b"
# model = "llama3.2:3b"

ollam_api_key = "ollama"


@tool
def multiplicador(a: int, b: int) -> int:
    """Multiplica dos números enteros."""
    return (a * b)

@tool
def decrementar(a: int, b: int) -> int:
    """Resta dos números enteros."""
    return (a - b)

@tool
def dividir(a: int, b: int) -> int:
    """Divide dos números enteros."""
    return (a / b)

tools = [multiplicador, decrementar, dividir]

tool_node = ToolNode(
    tools=tools,
)



# test_message = AIMessage(
#     content="",
#     tool_calls=[
#         {
#             "name": "multiplicador",
#             "args": {"a": 3, "b": 5},
#             "id": "tool_call_id",
#             "type": "tool_call",
#         }
#     ],
# )

# print(tool_node.invoke({"messages": [test_message]}))

llm = ChatOpenAI(
    model=model,
    base_url=ollama_endpoint,
    api_key=ollam_api_key,
    temperature=0.5,
)

llm_with_tools = llm.bind_tools(tools)


# print(llm_with_tools.invoke("what is the result of 3 * 5?").tool_calls)

# print(tool_node.invoke({"messages": [llm_with_tools.invoke("what is the result of 3 * 5?")]}))


def should_continue(state: MessagesState):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END


def call_model(state: MessagesState):
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


wk = StateGraph(MessagesState)
wk.add_node("agent", call_model)
wk.add_node("tools", tool_node)

wk.add_edge(START, "agent")
wk.add_conditional_edges("agent", should_continue, ["tools", END])
wk.add_edge("tools", "agent")

app = wk.compile()

# {"messages": [("human", "what's the weather in the coolest cities?")]}
# print(app.invoke({"messages": ["what is the result of 3 * 5?"]}, stream_mode="values")[-1].content)

# for chunk in app.stream(
#     {"messages": [("human", "what is the result of 3 * 5 minus 4 and then divide by 2 ?")]}, stream_mode="values"
# ):
#     chunk["messages"][-1].pretty_print()

# ================================ Human Message =================================

# what is the result of 3 * 5 minus 4 and then divide by 2 ?
# ================================== Ai Message ==================================

# Let me help you solve this step by step:

# 1. First, let's calculate \(3 \times 5\):
#    - Using the multiplicador tool with parameters a=3 and b=5:
#    - The result is: 15

# 2. Next, subtract 4 from the result:
#    - Using the decrementar tool with parameters a=15 and b=4:
#    - The new result is: 11

# 3. Finally, divide by 2:
#    - Using the dividir tool with parameters a=11 and b=2:
#    - The final result is: 5.5

# Therefore, \(3 \times 5 - 4\) divided by 2 equals 5.5.




