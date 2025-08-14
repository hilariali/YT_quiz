#!/usr/bin/env python3
"""
Simple test for the get_video_id function to validate current behavior
"""

def current_get_video_id(url: str) -> str:
    """
    Current implementation of get_video_id from streamlit_app.py
    """
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url.strip()

def test_current_implementation():
    """Test the current get_video_id implementation"""
    print("Testing current get_video_id implementation...")
    
    test_cases = [
        # Cases that should work with current implementation
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        
        # The problematic case from the issue
        ("https://www.youtube.com/live/Fw4rI_ljIzc", "Fw4rI_ljIzc"),
    ]
    
    print("\nCurrent implementation results:")
    for input_url, expected in test_cases:
        result = current_get_video_id(input_url)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"  {status}: '{input_url}' -> '{result}' (expected: '{expected}')")
        
        # Show what would happen in the download functions
        constructed_url = f"https://www.youtube.com/watch?v={result}"
        print(f"    Constructed URL: {constructed_url}")
        if "youtube.com" in result:
            print(f"    ⚠️  MALFORMED: Result contains full URL!")
        print()

if __name__ == "__main__":
    test_current_implementation()