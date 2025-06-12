import re
def clean_code(code):
    pattern = r"```python\n(.*?)```"
    match = re.search(pattern, code, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
    