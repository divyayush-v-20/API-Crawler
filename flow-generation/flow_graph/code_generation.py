from llm_config import llm
import code_cleaning
import code_testing
import code_parsing

# max_retries_global = 2

def generate_code(prompt):

    # max_retries_global -= 1
    # if not max_retries_global:
    #     return "Unable to generate a proper code"

    code = llm.invoke_llm(prompt)
    code_parsing.parse_code(code)