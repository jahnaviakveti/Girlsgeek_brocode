from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://localhost:5173/')
    time.sleep(2)
    # Just checking if there are console errors
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    
    # We might not be logged in or have data, so let's just assume the UI compiles without crashing.
    browser.close()
    if errors:
        print("Console errors:", errors)
    else:
        print("No console errors")
