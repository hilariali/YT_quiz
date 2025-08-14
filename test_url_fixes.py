#!/usr/bin/env python3
"""
Test suite for YouTube URL processing fixes.
Validates that the get_video_id function properly handles all YouTube URL formats.
"""

import re
import sys
import os

# Add the current directory to the path to import from streamlit_app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_video_id_extraction():
    """Test video ID extraction from various YouTube URL formats."""
    print("Testing YouTube URL processing...")
    
    # Test cases: (input_url, expected_video_id)
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
    
    # Import the current implementation
    try:
        from streamlit_app import get_video_id
        print("  Testing current implementation...")
        
        failed_tests = []
        for input_url, expected_id in test_cases:
            try:
                result = get_video_id(input_url)
                if result != expected_id:
                    failed_tests.append((input_url, expected_id, result))
                    print(f"  ❌ FAIL: {input_url} -> expected '{expected_id}', got '{result}'")
                else:
                    print(f"  ✅ PASS: {input_url} -> {result}")
            except Exception as e:
                failed_tests.append((input_url, expected_id, f"ERROR: {e}"))
                print(f"  ❌ ERROR: {input_url} -> {e}")
        
        if failed_tests:
            print(f"\n❌ {len(failed_tests)} tests failed out of {len(test_cases)}")
            return False
        else:
            print(f"\n✅ All {len(test_cases)} tests passed!")
            return True
            
    except ImportError as e:
        print(f"  ❌ Could not import get_video_id: {e}")
        return False

def test_video_id_validation():
    """Test that extracted video IDs are valid YouTube video IDs."""
    print("\nTesting video ID validation...")
    
    valid_ids = [
        "dQw4w9WgXcQ",  # 11 characters, alphanumeric + - _
        "Fw4rI_ljIzc",  # 11 characters with underscore
        "123456789AB",  # 11 characters
    ]
    
    invalid_inputs = [
        "",  # empty
        "short",  # too short
        "toolongtobeavalidyoutubevideoid",  # too long
        "invalid chars!",  # invalid characters
        "https://example.com/not-youtube",  # non-YouTube URL
    ]
    
    # Simple validation function to test against
    def is_valid_video_id(video_id):
        if not video_id:
            return False
        # YouTube video IDs are 11 characters long and contain only alphanumeric, dash, and underscore
        if len(video_id) != 11:
            return False
        return re.match(r'^[a-zA-Z0-9_-]+$', video_id) is not None
    
    print("  Valid video IDs:")
    for vid_id in valid_ids:
        valid = is_valid_video_id(vid_id)
        print(f"    {'✅' if valid else '❌'} {vid_id} -> {valid}")
    
    print("  Invalid inputs:")
    for invalid in invalid_inputs:
        valid = is_valid_video_id(invalid)
        print(f"    {'❌' if not valid else '⚠️'} '{invalid}' -> {valid}")
    
    return True

def test_malformed_url_issue():
    """Test the specific malformed URL issue mentioned in the problem statement."""
    print("\nTesting the specific malformed URL issue...")
    
    problematic_url = "https://www.youtube.com/live/Fw4rI_ljIzc"
    expected_video_id = "Fw4rI_ljIzc"
    
    try:
        from streamlit_app import get_video_id
        result = get_video_id(problematic_url)
        
        print(f"  Input URL: {problematic_url}")
        print(f"  Expected video ID: {expected_video_id}")
        print(f"  Actual result: {result}")
        
        # Check if result would cause the malformed URL issue
        constructed_url = f"https://www.youtube.com/watch?v={result}"
        print(f"  Constructed URL: {constructed_url}")
        
        if result == expected_video_id:
            print("  ✅ PASS: Correctly extracted video ID")
            return True
        else:
            print("  ❌ FAIL: Would cause malformed URL")
            return False
            
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

def run_all_tests():
    """Run all URL processing tests."""
    print("YouTube URL Processing Fix Tests")
    print("=" * 50)
    
    tests = [
        test_video_id_extraction,
        test_video_id_validation,
        test_malformed_url_issue
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with error: {e}")
    
    print("\n" + "=" * 50)
    if passed == len(tests):
        print("✅ All tests passed!")
        return True
    else:
        print(f"❌ {len(tests) - passed} out of {len(tests)} tests failed")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)