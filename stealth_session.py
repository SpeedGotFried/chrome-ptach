import asyncio
from playwright.async_api import async_playwright

async def handle_page(page, client_session_map):
    # Wait for the page to load or stabilize a bit
    await asyncio.sleep(0.5)
    if page.is_closed():
        return
        
    try:
        # Create a new CDP session for the page/tab
        client = await page.context.new_cdp_session(page)
        client_session_map[page] = client
        
        # Apply native CDP overrides
        await client.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
        await client.send("Page.setVisibilityState", {"visibilityState": "visible"})
        print(f"[+] Spoofed focus & visibility on: {page.url}")
    except Exception as e:
        # Ignore errors from pages that close immediately
        if "Target closed" not in str(e):
            print(f"[-] Error setting up CDP on page ({page.url}): {e}")

async def main():
    async with async_playwright() as p:
        print("[*] Connecting to Chrome at http://localhost:9222...")
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"\n[-] Failed to connect to Chrome: {e}")
            print("[!] Make sure Google Chrome is running in debugging mode on port 9222.")
            print("[!] Run launch_chrome.bat first.")
            return

        context = browser.contexts[0]
        client_session_map = {}

        # Apply overrides to all currently open pages/tabs
        for page in context.pages:
            await handle_page(page, client_session_map)

        # Listen for any new pages/tabs opened by the user
        context.on("page", lambda new_page: asyncio.create_task(handle_page(new_page, client_session_map)))

        print("[+] Active. Monitoring all current and future tabs. Keep this script running...")

        while True:
            await asyncio.sleep(1)
            # Remove closed pages from our session map to free memory
            for page in list(client_session_map.keys()):
                if page.is_closed():
                    client_session_map.pop(page, None)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Exiting stealth session.")
