import os
import sys
import threading
import time
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()

# Check token
token = os.getenv("OLLAMA_API_KEY")
if not token or token == "auth_token_":
    print("Error: OLLAMA_API_KEY is not set correctly in your .env file.")
    sys.exit(1)


# Import ChatOllama
try:
    from langchain_ollama import ChatOllama
except ImportError:
    try:
        from langchain_community.chat_models import ChatOllama
    except ImportError:
        print("Neither langchain_ollama nor langchain_community are installed.")
        print("Please run: pip install langchain-ollama")
        sys.exit(1)

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

import requests

# Query installed models on the server dynamically
MODELS = []
url = "https://gpu.snet.tu-berlin.de/echelon/ollama"
headers = {"Authorization": f"Bearer {token}"} if token else {}
try:
    resp = requests.get(f"{url.rstrip('/')}/api/tags", headers=headers, timeout=5)
    if resp.status_code == 200:
        MODELS = [m["name"] for m in resp.json().get("models", [])]
except Exception:
    pass

# Fallback
if not MODELS:
    MODELS = [
        "gemma4:26b",
        "gpt-oss:20b",
        "nemotron3:33b",
        "qwen3.6:35b",
        "gemma4:31b"
    ]


# Define Agent Layer Tools
class SecretCodeArgs(BaseModel):
    name: str = Field(description="Name of the person to get the secret code for")


def get_secret_code_fn(name: str) -> str:
    print(f"\n[Tool Execution] Calling get_secret_code for '{name}'...")
    return f"The secret code for {name} is: '{name.upper()}-SECRET-CODE-888'"


secret_code_tool = StructuredTool.from_function(
    func=get_secret_code_fn,
    name="get_secret_code",
    description="Retrieve a secret code for a person by their name.",
    args_schema=SecretCodeArgs,
)


class TrustFactorArgs(BaseModel):
    behavior_history: str = Field(description="A brief description of the person's behavior history")


def calculate_trust_factor_fn(behavior_history: str) -> str:
    print(f"\n[Tool Execution] Calling calculate_trust_factor based on history...")
    import random
    factor = random.randint(35, 98)
    return f"Analysis complete. Based on the behavior history, the calculated trust factor is: {factor}/100."


trust_factor_tool = StructuredTool.from_function(
    func=calculate_trust_factor_fn,
    name="calculate_trust_factor",
    description="Calculate a trust factor (1-100) based on a description of behavior history.",
    args_schema=TrustFactorArgs,
)


class ConsoleSpinner:
    def __init__(self, message="Thinking"):
        self.message = message
        self.spinner_cycle = ["|", "/", "-", "\\"] # Spinner for showing loading
        self.running = False
        self._thread = None

    def _spin(self):
        idx = 0
        while self.running:
            sys.stdout.write(f"\r{self.message} {self.spinner_cycle[idx]}")
            sys.stdout.flush()
            idx = (idx + 1) % len(self.spinner_cycle)
            time.sleep(0.15)
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._spin)
        self._thread.daemon = True
        self._thread.start()
        return self

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    print("=== Echelon Ollama Chat CLI Helper ===")
    print("Select a model to communicate with:")
    for idx, model in enumerate(MODELS, start=1):
        print(f"[{idx}] {model}")
        
    choice = input("\nEnter model number (default 1): ").strip()
    if not choice:
        model_name = MODELS[0]
    else:
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(MODELS):
                model_name = MODELS[choice_idx]
            else:
                print("Invalid selection. Using default model.")
                model_name = MODELS[0]
        except ValueError:
            print("Invalid input. Using default model.")
            model_name = MODELS[0]
            
    print("\nSelect interaction layer:")
    print("[1] Model Layer (Direct LLM Chat)")
    print("[2] Agent Layer (Agentic Loop with tools)")
    layer_choice = input("Enter layer choice (default 1): ").strip()
    is_agent_layer = (layer_choice == "2")
    layer_str = "Agent Layer" if is_agent_layer else "Model Layer"
            
    print(f"\nInitialized ChatOllama with model: '{model_name}' on [{layer_str}]")
    
    # Base URL points to the echelon server endpoint
    llm = ChatOllama(
        model=model_name,
        temperature=1.0,
        base_url="https://gpu.snet.tu-berlin.de/echelon/ollama",
        client_kwargs={
            "headers": {
                "Authorization": f"Bearer {token}"
            }
        }
    )
    
    tools = [secret_code_tool, trust_factor_tool]
    
    print("\nType your message below (type 'exit' or 'quit' to end):")
    if is_agent_layer:
        print("Note: Try asking the model to get a secret code or calculate a trust factor to see the tools execute!")
        
    # Initialize chat history or agent
    chat_history = []
    if is_agent_layer:
        from langchain.agents import create_agent
        system_prompt = (
            "You are a helpful AI Agent. You have access to tools for retrieving secret codes "
            "and calculating trust factors. Use these tools if the user asks for them, and "
            "present the results back to the user."
        )
        agent = create_agent(
            model=llm,
            system_prompt=system_prompt,
            tools=tools,
            middleware=[]
        )
    else:
        chat_history.append(
            SystemMessage(content="You are a helpful and conversational AI assistant.")
        )

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break
                
            # Append user's new message to the running history
            chat_history.append(HumanMessage(content=user_input))
            
            if not is_agent_layer:
                # 1. Model Layer Mode (Streaming chat with thinking text transition)
                print(f"\nOllama ({model_name}) is thinking...", end="", flush=True)
                full_content = []
                first_token = True
                try:
                    for chunk in llm.stream(chat_history):
                        content = chunk.content
                        if not content:
                            continue
                        if first_token:
                            # Clear
                            sys.stdout.write("\r" + " " * (len(model_name) + 30) + "\r")
                            sys.stdout.write("Ollama: ")
                            sys.stdout.flush()
                            first_token = False
                        print(content, end="", flush=True)
                        full_content.append(content)
                    print()
                    response = AIMessage(content="".join(full_content))
                except Exception:
                    # Fallback to invoke if streaming fails
                    sys.stdout.write("\n")
                    response = llm.invoke(chat_history)
                    print(response.content)
                chat_history.append(response)
            else:
                # 2. Agent Layer Mode
                tool_calls_detected = 0
                step_count = 0
                streamed_messages = []
                
                # initial thinking/loading of model
                spinner = ConsoleSpinner(f"Ollama ({model_name}) is thinking")
                spinner.start()
                
                try:
                    for event in agent.stream({"messages": chat_history}):
                        spinner.stop()
                        
                        for node_name, node_state in event.items():
                            messages = node_state.get("messages", [])
                            for msg in messages:
                                streamed_messages.append(msg)
                                if isinstance(msg, AIMessage):
                                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                                        for tc in msg.tool_calls:
                                            tool_calls_detected += 1
                                            print(f"  -> [Step {step_count+1}] Calling tool '{tc['name']}' with args: {tc['args']}...")
                                    elif msg.content:
                                        print(f"\nOllama:\n{msg.content}")
                                elif isinstance(msg, ToolMessage):
                                    print(f"  <- [Step {step_count+1}] Tool returned: {msg.content}")
                                    step_count += 1
                        
                        # Restart spinner for next step
                        spinner = ConsoleSpinner(f"Ollama ({model_name}) is thinking (Step {step_count+1})")
                        spinner.start()
                except Exception as e:
                    spinner.stop()
                    print(f"\nError during streaming: {e}")
                    # Fallback (if fails)
                    with ConsoleSpinner(f"Ollama ({model_name}) is thinking (fallback)"):
                        result = agent.invoke({"messages": chat_history})
                    streamed_messages = result.get("messages", [])[len(chat_history):]
                    for msg in streamed_messages:
                        if isinstance(msg, AIMessage) and msg.content:
                            print(f"\nOllama:\n{msg.content}")
                finally:
                    spinner.stop()
                            
                # Update running history 
                chat_history.extend(streamed_messages)
                        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError communicating with Ollama: {e}")

if __name__ == "__main__":
    main()

