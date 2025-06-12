from llm_config import llm
import code_cleaning
import re

def get_file_name(code):
    pattern = "python (.*?).py"
    match = re.search(pattern, code, re.DOTALL)
    if match:
        return match.group(1).strip()
    return "file"

def parse_code(code):

    file_name = get_file_name(code)
    code = code_cleaning.clean_code(code)
    prompt = f'''
        Check if the given code is correct wrt syntax\n
        If not, provide the corrected code, without changing any of the core\n
        functionality, just correcting the errors.\n

        IMPORTANT:\n
            1. Return the code block only and only if the code has errors\n
            and it was corrected/modified.\n
            2. If the code was correct(syntax), just return 1 word response as\n
            Correct.
        -----------------Code Below-------------------\n
        {code}
    '''

    result = llm.invoke_llm(prompt)
    if re.search("```python(.*?)```", result, re.DOTALL):
        code = result

    with open(f"../generated_codes/{file_name}.py", "w") as f:
        f.write(code)