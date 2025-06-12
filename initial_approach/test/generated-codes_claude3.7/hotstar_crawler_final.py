
def find_max_sum_subarray(arr, k):
    """
    Find the maximum sum of a subarray of size k.
    
    Args:
        arr: List of integers
        k: Size of the subarray
        
    Returns:
        Maximum sum of a subarray of size k
    """
    # Check if array length is less than k
    if len(arr) < k:
        return None
    
    # Calculate sum of first window of size k
    window_sum = sum(arr[:k])
    max_sum = window_sum
    
    # Slide the window from left to right
    for i in range(len(arr) - k):
        # Remove the leftmost element and add the rightmost element
        window_sum = window_sum - arr[i] + arr[i + k]
        # Update max_sum if current window sum is greater
        max_sum = max(max_sum, window_sum)
    
    return max_sum
