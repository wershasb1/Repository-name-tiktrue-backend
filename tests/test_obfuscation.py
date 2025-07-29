#!/usr/bin/env python3
"""
Simple test for PyArmor obfuscation
"""

def secret_function():
    """This function will be obfuscated"""
    secret_key = "TikTrue_Secret_Key_12345"
    return f"Secret processed: {len(secret_key)} characters"

def main():
    print("Testing PyArmor obfuscation...")
    result = secret_function()
    print(result)
    return 0

if __name__ == "__main__":
    main()