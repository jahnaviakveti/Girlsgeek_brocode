import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        errors = []
        page.on("pageerror", lambda err: errors.append(f"PageError: {err}"))
        page.on("console", lambda msg: errors.append(f"Console {msg.type}: {msg.text}") if msg.type in ["error"] else None)
        
        await page.goto("http://localhost:5173/")
        await page.wait_for_timeout(1000)
        
        # Navigate to Career Intelligence by clicking the nav tab
        await page.evaluate("""() => {
            const tabs = Array.from(document.querySelectorAll('.coach-nav-tab'));
            const ciTab = tabs.find(t => t.innerText && t.innerText.includes('Career Intelligence'));
            if (ciTab) ciTab.click();
            else console.error('CI TAB NOT FOUND');
        }""")
        
        await page.wait_for_timeout(2000)
        
        # Click the button
        print("Clicking + New Career Target")
        await page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const btn = btns.find(b => b.innerText && (b.innerText.includes('New Career Target') || b.innerText.includes('Create First Career Target')));
            if (btn) btn.click();
            else console.error('BUTTON NOT FOUND');
        }""")
        
        await page.wait_for_timeout(2000)
        
        print("--- CAPTURED ERRORS ---")
        for err in errors:
            print(err)
            
        await browser.close()

asyncio.run(main())
