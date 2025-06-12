#
# This script is compatible with Python 3.9 and higher.
#
import os
import hashlib
import json
import logging
import configparser
import boto3
from typing import Type

# LangChain Imports
from langchain_aws.chat_models import ChatBedrock
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import BaseTool, Tool # Import BaseTool for custom tools
from langchain_experimental.tools import PythonREPLTool
from langchain.prompts import PromptTemplate
from langchain import hub
from langchain.memory import ConversationSummaryBufferMemory

# Pydantic for custom tool validation
from pydantic import BaseModel, Field

# --- LangSmith and AWS Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Standard LangSmith tracing setup
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
# os.environ["LANGSMITH_API_KEY"] = "YOUR_LANGSMITH_API_KEY" # Uncomment and add your key if needed
os.environ["LANGSMITH_PROJECT"] = "api-crawler-generator-agent-py39"

def initialize_llm():
    """Initializes the Bedrock LLM using a specific AWS profile."""
    logging.info("Initializing Bedrock LLM with specified profile...")

    # NOTE: The profile name from your original code '536697239187-/AI-DEVELOPER' might be invalid
    # if it contains '/'. AWS profiles are typically alphanumeric with hyphens.
    # Please ensure this matches your `~/.aws/credentials` file.
    aws_profile_name = '536697239187-/AI-DEVELOPER'
    aws_region_name = 'us-east-1'
    credentials_file = os.path.expanduser('~/.aws/credentials')

    # Check if the credentials file exists
    if not os.path.exists(credentials_file):
        raise FileNotFoundError(f"AWS credentials file not found at: {credentials_file}")

    config = configparser.ConfigParser()
    config.read(credentials_file)

    if aws_profile_name not in config:
        raise ValueError(f"Profile '{aws_profile_name}' not found in {credentials_file}")

    # Create a boto3 session using the specified profile.
    # This is a robust way to handle credentials, including session tokens.
    try:
        session = boto3.Session(profile_name=aws_profile_name, region_name=aws_region_name)
        bedrock_runtime = session.client("bedrock-runtime")
    except Exception as e:
        logging.error(f"Failed to create boto3 session or client. Error: {e}")
        raise

    # Initialize the ChatBedrock model
    # Using the standard foundation model ID for Claude 3 Sonnet.
    llm = ChatBedrock(
        model_id="arn:aws:bedrock:us-east-1:536697239187:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        client=bedrock_runtime,
        model_kwargs={
            "max_tokens": 4096,
            "anthropic_version": "bedrock-2023-05-31",
            "temperature": 0.0
        }
    )
    logging.info("✅ Bedrock LLM initialized successfully.")
    return llm

# --- Custom Tools for the Agent ---

class WriteCodeInput(BaseModel):
    """Input schema for the WriteCodeToFileTool."""
    file_path: str = Field(description="The path, including the filename, where the Python code should be saved.")
    code: str = Field(description="The complete, final Python code to write to the file.")

class WriteCodeToFileTool(BaseTool):
    """A tool for the agent to save its final generated code to a file."""
    name: str = "write_code_to_file"
    description: str = "Writes the provided Python code to the specified file path. Use this only when the code is complete and verified."
    args_schema: Type[BaseModel] = WriteCodeInput

    def _run(self, file_path: str, code: str):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            return f"Successfully wrote code to {file_path}."
        except Exception as e:
            return f"Error writing file: {str(e)}"

# --- Main Generator Class using the Agent ---

class APICrawlerAgentGenerator:
    """
    Generates and maintains a Python web crawler script using a ReAct Agent
    based on provided API documentation.
    """
    GENERATED_CODE_DIR = "generated_codes"
    HASH_STORE_FILE = os.path.join(GENERATED_CODE_DIR, "code_hashes.json")

    def __init__(self, website_name: str, api_docs: str, llm: ChatBedrock):
        if not website_name or not website_name.isidentifier():
            raise ValueError("Website name must be a valid Python identifier.")

        self.website_name = website_name
        self.api_docs = api_docs
        self.llm = llm
        self.code_file_path = os.path.join(self.GENERATED_CODE_DIR, f"{self.website_name}_crawler.py")
        os.makedirs(self.GENERATED_CODE_DIR, exist_ok=True)

    def _load_hashes(self) -> dict:
        if not os.path.exists(self.HASH_STORE_FILE):
            return {}
        try:
            with open(self.HASH_STORE_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def _save_hash(self, file_hash: str):
        hashes = self._load_hashes()
        hashes[self.website_name] = file_hash
        with open(self.HASH_STORE_FILE, 'w') as f:
            json.dump(hashes, f, indent=4)

    def _get_file_hash(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _is_code_modified(self) -> bool:
        if not os.path.exists(self.code_file_path):
            return False
        stored_hash = self._load_hashes().get(self.website_name)
        if not stored_hash:
            return True
        return self._get_file_hash(self.code_file_path) != stored_hash

    def generate(self):
        """
        Main method to generate, correct, and save the crawler script using a ReAct agent.
        """
        logging.info(f"--- Starting Agent-based generator for '{self.website_name}' ---")

        if os.path.exists(self.code_file_path) and not self._is_code_modified():
            logging.info("✅ Code already exists and is unmodified. No action needed.")
            return

        # 1. Define the tools for the agent
        tools = [
            PythonREPLTool(),
            WriteCodeToFileTool()
        ]

        # 2. Pull the base prompt from LangChain Hub
        base_prompt = hub.pull("hwchase17/react-chat")

        # 3. Engineer the instructions for our specific task
        instructions = f"""
        You are an expert Python developer specializing in building API crawlers. Your primary goal is to write a complete, runnable Python script to crawl an API based on the provided documentation.

        **Follow these steps meticulously:**

        1.  **Analyze Documentation**: Carefully read the user's input containing the API documentation. Understand the base URL, authentication, and available endpoints.
        2.  **Plan the Script**: Formulate a clear plan. The script must include necessary imports (requests, os, json, logging), functions for each API task, and a main execution block.
        3.  **Write Code Incrementally**: Develop the Python code step-by-step. Do not attempt to write the entire script at once.
        4.  **Test Your Code**: After writing a piece of code (like a function), immediately use the `PythonREPLTool` to verify its syntax. Since you cannot make real API calls, you can test the logic by defining the function (e.g., `print("def my_func(): ...")`). This helps catch errors early.
        5.  **Refine and Correct**: If the `PythonREPLTool` returns an error, analyze the error message from the "Observation" and correct your code in the next step. This iterative correction is crucial.
        6.  **Final Script Requirements**: The final, complete script must:
            - Read the API key from an environment variable.
            - Contain functions to crawl the API.
            - Save the fetched data into a hierarchical JSON structure in an 'output' directory. (e.g., TV Shows: 'output/SHOW_NAME/S01E01.json', Movies: 'output/movies/MOVIE_NAME.json').
            - Be well-commented and include a `if __name__ == "__main__":` block to demonstrate usage.
        7.  **Save the Final Code**: Once you are fully confident in the complete, error-free script, use the `write_code_to_file` tool ONE TIME to save the final script to `{self.code_file_path}`. Do not use this tool for drafts.

        Begin now. The user has provided the API documentation.
        """
        prompt = base_prompt.partial(instructions=instructions)

        # 4. Create the Agent
        agent = create_react_agent(self.llm, tools, prompt)

        memory = ConversationSummaryBufferMemory(
            llm=self.llm, max_token_limit=2000, return_messages=True, memory_key="chat_history"
        )

        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            memory=memory,
            handle_parsing_errors=True,
            max_iterations=50
        )

        # 5. Invoke the Agent
        logging.info("Invoking agent to generate crawler script...")
        task = f"Here is the API Documentation. Please generate the Python crawler script.\n\n---\n\n{self.api_docs}"

        agent_executor.invoke({"input": task})

        # 6. Verify and store hash
        if os.path.exists(self.code_file_path):
            new_hash = self._get_file_hash(self.code_file_path)
            self._save_hash(new_hash)
            logging.info(f"✅ Agent finished. Stored new code hash for '{self.website_name}'.")
        else:
            logging.error("❌ Agent finished but failed to create the output file.")

        logging.info("--- Generator finished ---")


if __name__ == '__main__':
    # This is a fictional API documentation for demonstration purposes.
    cine_api_documentation = """
    Base URL: https://api.fictionalcineapi.com/v1

    Authentication:
    Include your API key in the 'x-api-key' header. The script should read the key from an environment variable named 'CINE_API_KEY'.

    Endpoints:
    1. Search: GET /search?q={query}&type={movie|show} -> Returns a JSON list of results. Each result must have 'id', 'title', and 'type'. Example: [{"id": "show_123", "title": "The Office", "type": "show"}]
    2. Movie Details: GET /movies/{movie_id} -> Returns a JSON object with full movie details. Example: {"id": "movie_456", "title": "Inception", "year": 2010, "director": "Christopher Nolan"}
    3. Show Episodes: GET /shows/{show_id}/episodes -> Returns a JSON list of all episodes for the show. Example: [{"id": "ep_789", "title": "Pilot", "season": 1, "episode": 1}]
    """

    try:
        llm_instance = initialize_llm()
        generator = APICrawlerAgentGenerator(
            website_name="cine_api",
            api_docs=cine_api_documentation,
            llm=llm_instance
        )
        generator.generate()

        print("\nAGENT RUN COMPLETE.")
        print(f"Check the generated_codes/ directory for the output script: {generator.code_file_path}")
        print("\nTo run the generated crawler, set the API key and execute the script:")
        print(f"export CINE_API_KEY='your_actual_api_key_here'")
        print(f"python {generator.code_file_path}")

    except Exception as e:
        logging.error(f"A critical error occurred in the main execution block: {e}", exc_info=True)
