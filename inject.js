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

  // 3. Intercept event listener registrations
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
          // Block visibilitychange completely
          return;
        }
        if (event.type === 'blur' || event.type === 'focusout') {
          // Only block blur/focusout if they target the window or document
          if (event.target === window || event.target === document) {
            return;
          }
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

  // 4. Disable onblur / onvisibilitychange properties
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
  blockHandlerProperty(document, 'onblur');
  blockHandlerProperty(document, 'onfocusout');
  blockHandlerProperty(document, 'onvisibilitychange');
  blockHandlerProperty(document, 'onwebkitvisibilitychange');
  blockHandlerProperty(Document.prototype, 'onblur');
  blockHandlerProperty(Document.prototype, 'onfocusout');
  blockHandlerProperty(Document.prototype, 'onvisibilitychange');
  blockHandlerProperty(Document.prototype, 'onwebkitvisibilitychange');

  console.log('[Always Focused & Visible] Bypass script successfully active.');
})();
