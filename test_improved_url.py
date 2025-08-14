#!/usr/bin/env python3
"""
Test the improved get_video_id function
"""

import sys
import os

# Add the current directory to the path to import from streamlit_app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_improved_implementation():
    """Test the improved get_video_id implementation"""
    print("Testing improved get_video_id implementation...")
    
    test_cases = [
        # Standard watch URLs
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("http://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLv3TTBr1W_9tppikBxAE_G6qjWdBljBHJ", "dQw4w9WgXcQ"),
        
        # Short URLs
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("http://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?t=30", "dQw4w9WgXcQ"),
        
        # Live URLs - this is the problematic format mentioned in the issue
        ("https://www.youtube.com/live/Fw4rI_ljIzc", "Fw4rI_ljIzc"),
        ("https://youtube.com/live/Fw4rI_ljIzc", "Fw4rI_ljIzc"),
        
        # Embed URLs
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ?start=30", "dQw4w9WgXcQ"),
        
        # Shorts URLs
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        
        # Already just video IDs
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("  dQw4w9WgXcQ  ", "dQw4w9WgXcQ"),  # with whitespace
        
        # Mobile URLs
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        
        # Gaming URLs
        ("https://gaming.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ]
    
    try:
        # Import the improved function
        from streamlit_app import get_video_id
        
        print("\nImproved implementation results:")
        failed_tests = []
        
        for input_url, expected in test_cases:
            result = get_video_id(input_url)
            status = "✅ PASS" if result == expected else "❌ FAIL"
            print(f"  {status}: '{input_url}' -> '{result}' (expected: '{expected}')")
            
            if result != expected:
                failed_tests.append((input_url, expected, result))
            
            # Show what would happen in the download functions
            constructed_url = f"https://www.youtube.com/watch?v={result}"
            if "youtube.com" in result:
                print(f"    ⚠️  MALFORMED: Result contains full URL!")
                print(f"    Constructed URL: {constructed_url}")
            elif result != expected:
                print(f"    Would construct: {constructed_url}")
            
        print(f"\nResults: {len(test_cases) - len(failed_tests)}/{len(test_cases)} tests passed")
        
        if failed_tests:
            print("\nFailed tests:")
            for input_url, expected, result in failed_tests:
                print(f"  {input_url} -> expected '{expected}', got '{result}'")
            return False
        else:
            print("🎉 All tests passed!")
            return True
            
    except Exception as e:
        print(f"❌ Error testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_malformed_url_fix():
    """Test that the specific malformed URL issue is fixed"""
    print("\n" + "="*50)
    print("Testing the specific malformed URL issue fix...")
    
    problematic_url = "https://www.youtube.com/live/Fw4rI_ljIzc"
    expected_video_id = "Fw4rI_ljIzc"
    
    try:
        from streamlit_app import get_video_id
        result = get_video_id(problematic_url)
        
        print(f"Input URL: {problematic_url}")
        print(f"Expected video ID: {expected_video_id}")
        print(f"Actual result: {result}")
        
        # Check if result would cause the malformed URL issue
        constructed_url = f"https://www.youtube.com/watch?v={result}"
        print(f"Constructed URL: {constructed_url}")
        
        if result == expected_video_id:
            print("✅ SUCCESS: Malformed URL issue is FIXED!")
            return True
        else:
            print("❌ FAIL: Would still cause malformed URL")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    success1 = test_improved_implementation()
    success2 = test_malformed_url_fix()
    
    if success1 and success2:
        print("\n🎉 All URL processing tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)