
def is_valid_parentheses(s):
    """
    Determine if a string of parentheses is valid.
    
    A string of parentheses is valid if:
    1. Open brackets must be closed by the same type of brackets.
    2. Open brackets must be closed in the correct order.
    3. Every close bracket has a corresponding open bracket of the same type.
    
    Args:
        s: A string containing just the characters '(', ')', '{', '}', '[' and ']'
        
    Returns:
        bool: True if the string is valid, False otherwise
    """
    # Initialize an empty stack to keep track of opening brackets
    stack = []
    
    # Define a mapping of closing brackets to their corresponding opening brackets
    bracket_map = {
        ')': '(',
        '}': '{',
        ']': '['
    }
    
    # Iterate through each character in the string
    for char in s:
        # If the character is a closing bracket
        if char in bracket_map:
            # Pop the top element from the stack if it's not empty, otherwise use a dummy value
            top_element = stack.pop() if stack else '#'
            
            # If the popped element doesn't match the corresponding opening bracket, return False
            if bracket_map[char] != top_element:
                return False
        else:
            # If the character is an opening bracket, push it onto the stack
            stack.append(char)
    
    # If the stack is empty, all brackets were properly closed
    return len(stack) == 0
