import os
import boto3
import configparser
from langchain_aws.chat_models import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
import dotenv
from botocore.config import Config
import ast
import subprocess
import json
from typing import Tuple

# --- Configuration and Setup ---
# This section remains the same as your original code for setting up AWS,
# Bedrock, and loading API documentation/credentials.

def setup_bedrock_llm():
    """Initializes and returns the Bedrock LLM client."""
    # Ensure AWS credentials are set up from environment or config files
    # For this example, we assume they are configured correctly
    # in ~/.aws/credentials and the profile is set.
    
    os.environ["AWS_SHARED_CREDENTIALS_FILE"] = '~/.aws/credentials'
    profile_name = '536697239187-/AI-DEVELOPER' # Your AWS profile
    os.environ["AWS_PROFILE"] = profile_name

    config = configparser.ConfigParser()
    config.read(os.path.expanduser('~/.aws/credentials'))

    if profile_name in config:
        os.environ['AWS_ACCESS_KEY_ID'] = config[profile_name]['aws_access_key_id']
        os.environ['AWS_SECRET_ACCESS_KEY'] = config[profile_name]['aws_secret_access_key']
        if 'aws_session_token' in config[profile_name]:
            os.environ['AWS_SESSION_TOKEN'] = config[profile_name]['aws_session_token']

    region_name = 'us-east-1'
    boto_config = Config(read_timeout=300, retries={'max_attempts': 3})
    
    bedrock_runtime = boto3.client(
        "bedrock-runtime",
        region_name=region_name,
        config=boto_config
    )

    llm = ChatBedrock(
        model_id="arn:aws:bedrock:us-east-1:536697239187:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        client=bedrock_runtime,
        provider="anthropic",
        model_kwargs={
            "max_tokens": 8000, # Increased for potentially larger code
            "anthropic_version": "bedrock-2023-05-31",
            "temperature": 0.1 # A little creativity might help fix bugs
        }
    )
    return llm

# --- Validation Engine ---
# These functions will test the generated code.

def validate_syntax(code_string: str) -> Tuple[bool, str]:
    """Checks if the generated code has valid Python syntax."""
    try:
        ast.parse(code_string)
        return True, "Syntax is valid."
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"

def validate_functionality(code_string: str, output_filename: str) -> Tuple[bool, str]:
    """
    Safely executes the generated code in a subprocess and checks if it
    produces the expected output file.
    WARNING: This runs external code. Subprocess provides some isolation,
    but ensure your execution environment is secure.
    """
    # Define the temporary script filename
    script_filename = "temp_generated_script.py"
    
    # Clean up old files before running
    if os.path.exists(script_filename):
        os.remove(script_filename)
    if os.path.exists(output_filename):
        os.remove(output_filename)

    # Write the generated code to a temporary file
    with open(script_filename, "w") as f:
        f.write(code_string)

    try:
        # Execute the script in a separate process with a timeout
        result = subprocess.run(
            ["python", script_filename],
            capture_output=True,
            text=True,
            timeout=120  # 2-minute timeout to prevent infinite loops
        )

        # Check for runtime errors
        if result.returncode != 0:
            error_message = f"Runtime Error:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            return False, error_message

        # Check if the expected output file was created
        if not os.path.exists(output_filename):
            return False, f"Functional Error: The script ran but did not create the output file '{output_filename}'."

        # Check if the output file is not empty
        if os.path.getsize(output_filename) == 0:
            return False, "Functional Error: The output file was created but is empty."
        
        # Optional: Check if the file contains valid JSON
        with open(output_filename, 'r') as f:
            try:
                json.load(f)
            except json.JSONDecodeError:
                return False, "Functional Error: The output file is not valid JSON."

        return True, "Functional Test Passed: Script executed successfully and created a valid, non-empty output file."

    except subprocess.TimeoutExpired:
        return False, "Functional Error: The script execution timed out (ran for more than 120 seconds)."
    finally:
        # Clean up the temporary script
        if os.path.exists(script_filename):
            os.remove(script_filename)


# --- Orchestrator ---

def main():
    """Main orchestration function."""
    print("--- Starting Automated Code Generation Flow for YLE ---")
    
    # 1. Initialize LLM and load data
    llm = setup_bedrock_llm()
    dotenv.load_dotenv()
    
    try:
        with open("../API-Documentations/YLE.txt", "r") as f:
            yle_file = f.read()
    except FileNotFoundError:
        print("Error: 'API-Documentations/YLE.txt' not found. Please ensure the file exists.")
        return
    
    # Define file paths for YLE
    output_dir = "results_claude3.7/yle"
    final_code_dir = "generated-codes_claude3.7"
    expected_json_output = os.path.join(output_dir, "yle_data.json")
    final_code_path = os.path.join(final_code_dir, "yle_crawler_final.py")

    # Ensure directories exist
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(final_code_dir, exist_ok=True)

    # 2. Define Prompts using LangChain for YLE
    initial_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="You are an expert Python developer. Your task is to write a web crawler script based on the provided API documentation. The response must ONLY be the Python code itself, with no extra text or explanations."),
        HumanMessage(content="""
        Generate a complete, runnable Python script to crawl the YLE API.

        CRAWLING INSTRUCTIONS:
        1. Crawl hierarchically: genre -> show -> episodes.
        2. Create a directory named '{output_dir}' if it doesn't exist.
        3. Save the final crawled data as a single JSON file at '{output_filename}'.
        4. The script must import all necessary libraries (like `os`, `requests`, `json`).
        5. Just identify the shows and movies, i.e., the relevant data.

        API Documentation:
        ---
        {api_docs}
        ---
        """)
    ])

    feedback_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="You are an expert Python developer. Your previous code failed some tests. Analyze the error, fix the code, and return the complete, corrected script. Only output the Python code."),
        HumanMessage(content="""
        The following Python code you generated has an error.

        Previous Code:
        ```python
        {previous_code}
        ```

        Validation Error:
        ---
        {feedback}
        ---

        Please fix the code and provide the full, corrected Python script.
        """)
    ])
    
    # 3. The Generation and Validation Loop
    max_attempts = 3
    generated_code = ""
    feedback = ""
    
    for attempt in range(max_attempts):
        print(f"\n--- 🚀 Attempt {attempt + 1} of {max_attempts} ---")
        
        if attempt == 0:
            print("Generating initial code...")
            prompt = initial_prompt.format_messages(
                output_dir=output_dir,
                output_filename=expected_json_output,
                api_docs=yle_file
            )
        else:
            print("Regenerating code based on feedback...")
            prompt = feedback_prompt.format_messages(
                previous_code=generated_code,
                feedback=feedback
            )
            
        response = llm.invoke(prompt)
        generated_code = response.content.strip()

        # Remove markdown fences if the LLM includes them
        if generated_code.startswith("```python"):
            generated_code = generated_code[9:]
        if generated_code.endswith("```"):
            generated_code = generated_code[:-3]
        
        print("--- 🧪 Running Validations ---")
        
        # Test 1: Syntax Check
        is_valid_syntax, syntax_feedback = validate_syntax(generated_code)
        print(f"Syntax Check: {'PASS' if is_valid_syntax else 'FAIL'}")
        if not is_valid_syntax:
            feedback = syntax_feedback
            continue # Go to the next attempt

        # Test 2: Functional Check
        is_functional, func_feedback = validate_functionality(generated_code, expected_json_output)
        print(f"Functional Check: {'PASS' if is_functional else 'FAIL'}")
        if not is_functional:
            feedback = func_feedback
            continue # Go to the next attempt

        # If all tests pass
        print("\n--- ✅ All Validations Passed! ---")
        break
    
    # 4. Final Output
    print("\n--- ✨ Final Result ---")
    if feedback: # This means the loop finished without all tests passing
        print("Could not generate a fully validated script after all attempts.")
        print(f"Last encountered error: {feedback}")
    else:
        print("Successfully generated and validated the crawler script.")

    print(f"Saving final code to: {final_code_path}")
    with open(final_code_path, "w") as f:
        f.write(generated_code)
    
    print("\nFinal Code:")
    print("-" * 20)
    print(generated_code)
    print("-" * 20)

if __name__ == "__main__":
    main()
