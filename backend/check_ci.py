from playwright.sync_api import sync_playwright
import time

def check():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:5173/")
        time.sleep(2) # let it load
        page.screenshot(path="screenshot.png")
        browser.close()
check()
