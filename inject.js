(function() {
  'use strict';

  console.log('[Always Focused & Visible] Injecting bypass script...');

  const defineProp = (obj, prop, val) => {
    try {
      Object.defineProperty(obj, prop, {
        get: () => val,
        set: () => {},
        configurable: true,
        enumerable: true
      });
    } catch (e) {
      console.warn(`[Always Focused & Visible] Failed to override ${prop}:`, e);
    }
  };

  // 1. Override document visibility properties
  defineProp(document, 'hidden', false);
  defineProp(document, 'visibilityState', 'visible');
  defineProp(Document.prototype, 'hidden', false);
  defineProp(Document.prototype, 'visibilityState', 'visible');

  // Vendor prefixed properties (legacy compatibility)
  defineProp(document, 'webkitHidden', false);
  defineProp(document, 'webkitVisibilityState', 'visible');
  defineProp(Document.prototype, 'webkitHidden', false);
  defineProp(Document.prototype, 'webkitVisibilityState', 'visible');

  // 2. Override document.hasFocus()
  try {
    document.hasFocus = () => true;
    Document.prototype.hasFocus = () => true;
  } catch (e) {
    console.warn('[Always Focused & Visible] Failed to override hasFocus:', e);
  }

  // 3. Helper to detect key events used for taking screenshots or launching tools
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

  // 4. Intercept event listener registrations
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
          // Block visibilitychange completely
          return;
        }
        if (event.type === 'blur' || event.type === 'focusout') {
          // Only block blur/focusout if they target the window or document
          if (event.target === window || event.target === document) {
            return;
          }
        }
        if (isMouseEvent) {
          // Block mouse tracking/leave events at window/document level completely
          return;
        }
        if (isKeyboardEvent) {
          // Only block screenshot or inspection keyboard triggers
          if (isSurveillanceKeyEvent(event)) {
            event.preventDefault();
            event.stopPropagation();
            return;
          }
        }
        if (event.type === 'contextmenu') {
          // Block website attempts to disable right-click menu
          return;
        }
        return listener.apply(this, arguments);
      };

      // Store association for removeEventListener
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

  // 5. Disable onblur / onvisibilitychange / onmousemove / oncontextmenu properties
  const blockHandlerProperty = (obj, prop) => {
    try {
      Object.defineProperty(obj, prop, {
        get: () => null,
        set: () => {},
        configurable: true,
        enumerable: true
      });
    } catch (e) {
      console.warn(`[Always Focused & Visible] Failed to block handler property ${prop}:`, e);
    }
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
  blockHandlerProperty(Document.prototype, 'onblur');
  blockHandlerProperty(Document.prototype, 'onfocusout');
  blockHandlerProperty(Document.prototype, 'onvisibilitychange');
  blockHandlerProperty(Document.prototype, 'onwebkitvisibilitychange');
  blockHandlerProperty(Document.prototype, 'oncontextmenu');

  // 6. Force User Select CSS rules to override copy/paste & text selection blocks
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

  console.log('[Always Focused & Visible] Bypass script successfully active.');
})();
