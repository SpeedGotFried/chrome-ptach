import asyncio
from playwright.async_api import async_playwright

# Stealth JS overrides script to run on every document initialization (before page JS runs)
STEALTH_JS_SCRIPT = """
(function() {
  const originalToString = Function.prototype.toString;
  const mocks = new Map();
  
  const mockFunction = (obj, prop, implementation) => {
    try {
      const original = obj[prop];
      obj[prop] = implementation;
      mocks.set(implementation, originalToString.call(original));
    } catch (e) {}
  };

  // Mock hasFocus to always be true
  mockFunction(document, 'hasFocus', () => true);
  if (window.Document && Document.prototype) {
    mockFunction(Document.prototype, 'hasFocus', () => true);
  }

  // Helper to safely define a property getter
  const defineProp = (obj, prop, val) => {
    try {
      Object.defineProperty(obj, prop, {
        get: () => val,
        set: () => {},
        configurable: true,
        enumerable: true
      });
    } catch (e) {}
  };

  // Mock document visibility properties
  defineProp(document, 'hidden', false);
  defineProp(document, 'visibilityState', 'visible');
  defineProp(document, 'webkitHidden', false);
  defineProp(document, 'webkitVisibilityState', 'visible');

  if (window.Document && Document.prototype) {
    defineProp(Document.prototype, 'hidden', false);
    defineProp(Document.prototype, 'visibilityState', 'visible');
    defineProp(Document.prototype, 'webkitHidden', false);
    defineProp(Document.prototype, 'webkitVisibilityState', 'visible');
  }

  // Intercept event listener registrations
  const originalAddEventListener = EventTarget.prototype.addEventListener;
  const originalRemoveEventListener = EventTarget.prototype.removeEventListener;
  const wrappedListeners = new WeakMap();

  EventTarget.prototype.addEventListener = function(type, listener, options) {
    if (typeof listener !== 'function') {
      return originalAddEventListener.apply(this, arguments);
    }

    const isTargetWindowOrDoc = (
      this === window || 
      this === document || 
      this instanceof Document || 
      this instanceof Window
    );

    const shouldBlock = 
      (type === 'visibilitychange') ||
      (type === 'webkitvisibilitychange') ||
      (isTargetWindowOrDoc && (type === 'blur' || type === 'focusout'));

    if (shouldBlock) {
      const wrappedListener = function(event) {
        if (event.type === 'visibilitychange' || event.type === 'webkitvisibilitychange') {
          return; // Suppress
        }
        if (event.type === 'blur' || event.type === 'focusout') {
          if (event.target === window || event.target === document) {
            return; // Suppress window/document blur
          }
        }
        return listener.apply(this, arguments);
      };

      let targetMap = wrappedListeners.get(this);
      if (!targetMap) {
        targetMap = new Map();
        wrappedListeners.set(this, targetMap);
      }
      targetMap.set(listener, wrappedListener);

      return originalAddEventListener.call(this, type, wrappedListener, options);
    }

    return originalAddEventListener.apply(this, arguments);
  };

  EventTarget.prototype.removeEventListener = function(type, listener, options) {
    const targetMap = wrappedListeners.get(this);
    if (targetMap && targetMap.has(listener)) {
      const wrappedListener = targetMap.get(listener);
      targetMap.delete(listener);
      return originalRemoveEventListener.call(this, type, wrappedListener, options);
    }
    return originalRemoveEventListener.apply(this, arguments);
  };

  // Block handler properties
  const blockHandlerProperty = (obj, prop) => {
    try {
      Object.defineProperty(obj, prop, {
        get: () => null,
        set: () => {},
        configurable: true,
        enumerable: true
      });
    } catch (e) {}
  };

  blockHandlerProperty(window, 'onblur');
  blockHandlerProperty(window, 'onfocusout');
  blockHandlerProperty(document, 'onblur');
  blockHandlerProperty(document, 'onfocusout');
  blockHandlerProperty(document, 'onvisibilitychange');
  blockHandlerProperty(document, 'onwebkitvisibilitychange');

  if (window.Document && Document.prototype) {
    blockHandlerProperty(Document.prototype, 'onblur');
    blockHandlerProperty(Document.prototype, 'onfocusout');
    blockHandlerProperty(Document.prototype, 'onvisibilitychange');
    blockHandlerProperty(Document.prototype, 'onwebkitvisibilitychange');
  }

  // Restore custom toString representation for our mocks
  Function.prototype.toString = function() {
    if (mocks.has(this)) {
      return mocks.get(this);
    }
    return originalToString.apply(this, arguments);
  };
})();
"""

async def handle_page(page, client_session_map):
    await asyncio.sleep(0.2)
    if page.is_closed():
        return
        
    try:
        # Create a new CDP session for the page/tab
        client = await page.context.new_cdp_session(page)
        client_session_map[page] = client
        
        # 1. Native CDP command to evaluate script on every new document (navigation) in this tab
        await client.send("Page.addScriptToEvaluateOnNewDocument", {"source": STEALTH_JS_SCRIPT})
        
        # 2. Run overrides immediately in case the page is already loaded
        await client.send("Runtime.evaluate", {
            "expression": STEALTH_JS_SCRIPT,
            "userGesture": True,
            "awaitPromise": False
        })
        
        # 3. Apply native CDP overrides
        await client.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
        await client.send("Page.setVisibilityState", {"visibilityState": "visible"})
        
        # 4. Set up a listener to re-apply emulation on navigation (since navigation resets it)
        async def on_navigate(frame):
            if frame == page.main_frame:
                await asyncio.sleep(0.1)
                try:
                    await client.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
                    await client.send("Page.setVisibilityState", {"visibilityState": "visible"})
                except Exception:
                    pass

        page.on("framenavigated", lambda frame: asyncio.create_task(on_navigate(frame)))
        print(f"[+] Spoofed focus & visibility on: {page.url}")
    except Exception as e:
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
