#!/usr/bin/env python3
"""
Standalone test for the improved get_video_id function
"""

import re

def get_video_id(url: str) -> str:
    """
    Extract YouTube video ID from URL or return input if already an ID.
    Supports all YouTube URL formats including live, shorts, embed, and mobile URLs.
    """
    # Clean up the input
    url = url.strip()
    
    # If it's already a video ID (11 characters, alphanumeric + - _), return it
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url
    
    # YouTube video ID regex patterns for different URL formats
    patterns = [
        # Standard watch URLs: youtube.com/watch?v=VIDEO_ID
        r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        
        # Short URLs: youtu.be/VIDEO_ID
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        
        # Live URLs: youtube.com/live/VIDEO_ID
        r'(?:youtube\.com/live/)([a-zA-Z0-9_-]{11})',
        
        # Embed URLs: youtube.com/embed/VIDEO_ID
        r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        
        # Shorts URLs: youtube.com/shorts/VIDEO_ID
        r'(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        
        # Mobile URLs: m.youtube.com/watch?v=VIDEO_ID
        r'(?:m\.youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        
        # Gaming URLs: gaming.youtube.com/watch?v=VIDEO_ID
        r'(?:gaming\.youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
    ]
    
    # Try each pattern
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # If no pattern matches and it looks like a YouTube URL, try fallback extraction
    if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
        # Last resort: look for any 11-character alphanumeric sequence that could be a video ID
        fallback_match = re.search(r'([a-zA-Z0-9_-]{11})', url)
        if fallback_match:
            return fallback_match.group(1)
    
    # If nothing else works, return the original input stripped
    # This maintains backward compatibility
    return url

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
    
    print("\nImproved implementation results:")
    failed_tests = []
    
    for input_url, expected in test_cases:
        result = get_video_id(input_url)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"  {status}: '{input_url}' -> '{result}' (expected: '{expected}')")
        
        if result != expected:
            failed_tests.append((input_url, expected, result))
        
        # Check for malformed URL issue
        if "youtube.com" in result:
            print(f"    ⚠️  MALFORMED: Result contains full URL!")
    
    print(f"\nResults: {len(test_cases) - len(failed_tests)}/{len(test_cases)} tests passed")
    
    if failed_tests:
        print("\nFailed tests:")
        for input_url, expected, result in failed_tests:
            print(f"  {input_url} -> expected '{expected}', got '{result}'")
        return False
    else:
        print("🎉 All tests passed!")
        return True

def test_malformed_url_fix():
    """Test that the specific malformed URL issue is fixed"""
    print("\n" + "="*50)
    print("Testing the specific malformed URL issue fix...")
    
    problematic_url = "https://www.youtube.com/live/Fw4rI_ljIzc"
    expected_video_id = "Fw4rI_ljIzc"
    
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

if __name__ == "__main__":
    success1 = test_improved_implementation()
    success2 = test_malformed_url_fix()
    
    if success1 and success2:
        print("\n🎉 All URL processing tests passed!")
    else:
        print("\n❌ Some tests failed")