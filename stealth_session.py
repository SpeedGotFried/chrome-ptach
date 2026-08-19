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

  // Helper to detect key events used for taking screenshots or launching tools
  const isSurveillanceKeyEvent = (e) => {
    const key = e.key;
    // Block PrintScreen, Win key, Function keys F1-F12, and ContextMenu key
    if (key === 'PrintScreen' || key === 'OS' || key === 'Meta' || (key && key.startsWith('F')) || key === 'ContextMenu') {
      return true;
    }
    // Block standard DevTools key combinations (Ctrl+Shift+I, J, C, K) and View Source (Ctrl+U)
    if (e.ctrlKey && (e.shiftKey && ['I', 'J', 'C', 'K', 'i', 'j', 'c', 'k'].includes(e.key) || ['U', 'u'].includes(e.key))) {
      return true;
    }
    return false;
  };

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

    const isMouseEvent = (type === 'mousemove' || type === 'mouseleave' || type === 'mouseout' || type === 'mouseenter');
    const isKeyboardEvent = (type === 'keydown' || type === 'keyup' || type === 'keypress');

    const shouldBlock = 
      (type === 'visibilitychange') ||
      (type === 'webkitvisibilitychange') ||
      (isTargetWindowOrDoc && (type === 'blur' || type === 'focusout')) ||
      (isTargetWindowOrDoc && isMouseEvent) ||
      (isTargetWindowOrDoc && isKeyboardEvent) ||
      (type === 'contextmenu');

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
        if (isMouseEvent) {
          return; // Suppress mouse tracking/leave events
        }
        if (isKeyboardEvent) {
          if (isSurveillanceKeyEvent(event)) {
            event.preventDefault();
            event.stopPropagation();
            return;
          }
        }
        if (event.type === 'contextmenu') {
          return; // Suppress right-click blocking
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
  blockHandlerProperty(window, 'onmouseleave');
  blockHandlerProperty(window, 'onmouseout');
  blockHandlerProperty(window, 'oncontextmenu');
  blockHandlerProperty(document, 'onblur');
  blockHandlerProperty(document, 'onfocusout');
  blockHandlerProperty(document, 'onvisibilitychange');
  blockHandlerProperty(document, 'onwebkitvisibilitychange');
  blockHandlerProperty(document, 'onmousemove');
  blockHandlerProperty(document, 'onmouseleave');
  blockHandlerProperty(document, 'onmouseout');
  blockHandlerProperty(document, 'oncontextmenu');

  if (window.Document && Document.prototype) {
    blockHandlerProperty(Document.prototype, 'onblur');
    blockHandlerProperty(Document.prototype, 'onfocusout');
    blockHandlerProperty(Document.prototype, 'onvisibilitychange');
    blockHandlerProperty(Document.prototype, 'onwebkitvisibilitychange');
    blockHandlerProperty(Document.prototype, 'oncontextmenu');
  }

  // Force text selection styles
  const forceTextSelection = () => {
    const style = document.createElement('style');
    style.id = '__always_selectable_css__';
    style.textContent = `
      * {
        -webkit-user-select: text !important;
        -moz-user-select: text !important;
        -ms-user-select: text !important;
        user-select: text !important;
      }
    `;
    if (document.head) {
      document.head.appendChild(style);
    } else {
      document.documentElement.appendChild(style);
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', forceTextSelection);
  } else {
    forceTextSelection();
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
    import os
    import tempfile
    
    port = 9222
    temp_file_path = os.path.join(tempfile.gettempdir(), "chrome_stealth_port.txt")
    if os.path.exists(temp_file_path):
        try:
            with open(temp_file_path, "r") as f:
                port = int(f.read().strip())
                print(f"[+] Found dynamically generated port in temp file: {port}")
        except Exception as e:
            print(f"[-] Could not read port from temp file, defaulting to 9222. Error: {e}")
    else:
        print("[*] Temp port file not found. Defaulting to standard port 9222...")

    async with async_playwright() as p:
        print(f"[*] Connecting to Chrome at http://localhost:{port}...")
        try:
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{port}")
        except Exception as e:
            print(f"\n[-] Failed to connect to Chrome: {e}")
            print(f"[!] Make sure Google Chrome is running in debugging mode on port {port}.")
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
