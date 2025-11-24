/**
 * Automatic Page Encryption Script
 * Encrypts all text on any webpage with a single API call
 * 
 * Usage: Just include this script on any webpage:
 * <script src="https://your-api.com/client/encrypt-page.js"></script>
 * 
 * Configuration (optional, via data attributes on script tag):
 * <script src="..." data-api-url="https://your-api.com/api/encrypt/page" data-secret-key="29202393"></script>
 */
(function() {
    'use strict';
    
    // ============================================================================
    // CONFIGURATION
    // ============================================================================
    const CONFIG = {
        // Default secret key (can be overridden via data-secret-key attribute)
        // If not specified, API will use server default
        secretKey: null,
        
        // Font name for encrypted content
        fontName: 'EncryptedFont',
        
        // Elements to skip (don't encrypt text in these)
        skipSelectors: [
            'script',
            'style',
            'noscript',
            'meta',
            'title',
            'head',
            '.no-encrypt',
            '[data-no-encrypt]'
        ],
        
        // Minimum text length to encrypt (skip very short content)
        minTextLength: 1
    };
    
    // Get configuration from script tag data attributes and auto-detect API URL
    const currentScript = document.currentScript || 
        document.querySelector('script[src*="encrypt-page"]') ||
        document.querySelector('script[src*="encrypt-page.js"]');
    
    // Auto-detect API endpoint from script URL
    let apiEndpoint = '/api/encrypt/page'; // Default relative path
    if (currentScript && currentScript.src) {
        try {
            const scriptUrl = new URL(currentScript.src);
            // Build API URL from script URL (e.g., /client/encrypt-page.js -> /api/encrypt/page)
            apiEndpoint = `${scriptUrl.origin}/api/encrypt/page`;
        } catch (e) {
            // If URL parsing fails, use relative path
            apiEndpoint = '/api/encrypt/page';
        }
    }
    
    if (currentScript) {
        if (currentScript.dataset.apiUrl) {
            apiEndpoint = currentScript.dataset.apiUrl;
        }
        if (currentScript.dataset.secretKey) {
            CONFIG.secretKey = parseInt(currentScript.dataset.secretKey);
        }
    }
    
    CONFIG.apiEndpoint = apiEndpoint;
    
    // ============================================================================
    // DECRYPTION MAPPINGS (for copy-paste functionality)
    // Secure storage using closure to prevent direct access
    // ============================================================================
    
    // Use Symbol-based keys to prevent enumeration
    const MAP_STORE = Symbol('mappingStore');
    const NONCE_STORE = Symbol('nonceStore');
    const KEY_STORE = Symbol('keyStore');
    
    // Private storage in closure
    const mappingStore = {
        [MAP_STORE]: {
            upper: null,
            lower: null,
            space: null
        },
        [NONCE_STORE]: null,
        [KEY_STORE]: null
    };
    
    /**
     * Store decryption mappings from API response
     * Uses secure storage to prevent direct access
     */
    function storeDecryptionMappings(upperMap, lowerMap, spaceMap, nonce, secretKey) {
        // Create reverse mappings for fast decryption
        const reverseUpper = {};
        const reverseLower = {};
        const reverseSpace = {};
        
        // Reverse upper_map: encrypted -> original
        for (const [original, encrypted] of Object.entries(upperMap)) {
            reverseUpper[encrypted] = original;
        }
        
        // Reverse lower_map: encrypted -> original (includes space)
        for (const [original, encrypted] of Object.entries(lowerMap)) {
            reverseLower[encrypted] = original;
        }
        
        // Reverse space_map: encrypted -> original
        for (const [original, encrypted] of Object.entries(spaceMap)) {
            reverseSpace[encrypted] = original;
        }
        
        // Store in secure closure
        mappingStore[MAP_STORE] = {
            upper: reverseUpper,
            lower: reverseLower,
            space: reverseSpace
        };
        mappingStore[NONCE_STORE] = nonce;
        mappingStore[KEY_STORE] = secretKey || CONFIG.secretKey;
    }
    
    /**
     * Get reverse mappings (encrypted -> original) for decryption
     * Returns null if mappings not available
     */
    function getReverseMappings() {
        const maps = mappingStore[MAP_STORE];
        if (!maps || !maps.upper || !maps.lower) {
            return null;
        }
        // Return a copy to prevent external modification
        return {
            upper: Object.assign({}, maps.upper),
            lower: Object.assign({}, maps.lower),
            space: Object.assign({}, maps.space)
        };
        }
        
    /**
     * Compute forward mappings (original -> encrypted) from reverse mappings
     * Computed on-the-fly and not stored for security
     * Returns null if reverse mappings not available
     */
    function computeForwardMapping() {
        const reverseMaps = mappingStore[MAP_STORE];
        if (!reverseMaps || !reverseMaps.upper || !reverseMaps.lower) {
            return null;
        }
        
        // Invert reverse mappings to get forward mappings
        const forwardUpper = {};
        const forwardLower = {};
        const forwardSpace = {};
        
        // Invert upper: for each encrypted->original, create original->encrypted
        for (const [encrypted, original] of Object.entries(reverseMaps.upper)) {
            forwardUpper[original] = encrypted;
        }
        
        // Invert lower: for each encrypted->original, create original->encrypted
        for (const [encrypted, original] of Object.entries(reverseMaps.lower)) {
            forwardLower[original] = encrypted;
        }
        
        // Invert space: for each encrypted->original, create original->encrypted
        for (const [encrypted, original] of Object.entries(reverseMaps.space)) {
            forwardSpace[original] = encrypted;
        }
        
        return {
            upper: forwardUpper,
            lower: forwardLower,
            space: forwardSpace
        };
    }
    
    /**
     * Decrypt text using stored reverse mappings
     * Handles zero-width spaces and special characters
     */
    function decryptText(encryptedText) {
        const reverseMaps = mappingStore[MAP_STORE];
        if (!reverseMaps || !reverseMaps.upper || !reverseMaps.lower) {
            // Mappings not available, return as-is
            return encryptedText;
        }
        
        // Remove zero-width spaces (U+200B) that were inserted for word-breaking
        const textWithoutZWSP = encryptedText.replace(/\u200B/g, '');
        
        // Decrypt character by character
        const result = [];
        for (const char of textWithoutZWSP) {
            // Check uppercase first
            if (char in reverseMaps.upper) {
                result.push(reverseMaps.upper[char]);
            }
            // Check lowercase or space (space is in lower_map)
            else if (char in reverseMaps.lower) {
                result.push(reverseMaps.lower[char]);
            }
            // Check special characters
            else if (char in reverseMaps.space) {
                result.push(reverseMaps.space[char]);
            }
            // Handle newline (maps to null in some cases)
            else if (char === '\n') {
                result.push('\x00');
            }
            // Keep unmapped characters as-is
            else {
                result.push(char);
            }
        }
        
        return result.join('');
    }
    
    // ============================================================================
    // TEXT EXTRACTION
    // ============================================================================
    
    /**
     * Check if a text node is at the start of a new line.
     * A text node is at line start if:
     * 1. It's the first child of its parent, OR
     * 2. The previous sibling is a block element or <br> tag, OR
     * 3. All previous siblings are whitespace-only and we're the first non-whitespace content
     * 4. We're the first non-whitespace content in a block element (even if nested in inline elements)
     */
    function isTextAtLineStart(textNode) {
        if (!textNode || !textNode.parentElement) {
            return false;
        }
        
        const parent = textNode.parentElement;
        
        // Block-level elements that cause line breaks
        const blockElements = [
            'DIV', 'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
            'UL', 'OL', 'LI', 'BLOCKQUOTE', 'PRE', 'SECTION',
            'ARTICLE', 'HEADER', 'FOOTER', 'NAV', 'ASIDE',
            'TABLE', 'TR', 'TD', 'TH', 'THEAD', 'TBODY', 'TFOOT',
            'DL', 'DT', 'DD', 'FORM', 'FIELDSET', 'LEGEND',
            'ADDRESS', 'HR', 'FIGURE', 'FIGCAPTION', 'BODY'
        ];
        
        // Helper to check if an element has visible text content
        function hasVisibleContent(elem) {
            if (elem.nodeType === Node.ELEMENT_NODE) {
                return elem.textContent.trim().length > 0;
            } else if (elem.nodeType === Node.TEXT_NODE) {
                return elem.textContent.trim().length > 0;
            }
            return false;
        }
        
        // Check if this is the first child
        if (!parent.firstChild || parent.firstChild === textNode) {
            return true;
        }
        
        // Find the previous sibling
        let prevSibling = textNode.previousSibling;
        
        // Skip over whitespace-only text nodes
        while (prevSibling) {
            if (prevSibling.nodeType === Node.ELEMENT_NODE) {
                // It's an element
                if (prevSibling.tagName === 'BR') {
                    return true;
                }
                if (blockElements.includes(prevSibling.tagName)) {
                    return true;
                }
                // If it's an inline element, check if it has visible content
                if (hasVisibleContent(prevSibling)) {
                    return false;
                }
                // Empty inline element, continue checking
                prevSibling = prevSibling.previousSibling;
            } else if (prevSibling.nodeType === Node.TEXT_NODE) {
                // It's a text node - check if it's only whitespace
                if (hasVisibleContent(prevSibling)) {
                    return false;
                }
                // Whitespace text, continue checking
                prevSibling = prevSibling.previousSibling;
            } else {
                break;
            }
        }
        
        // If we got here, all previous siblings were whitespace or None
        // Now walk up the tree to find block element ancestors and check if we're first content
        let current = parent;
        while (current) {
            if (current.nodeType === Node.ELEMENT_NODE && blockElements.includes(current.tagName)) {
                // Found a block element - check if we're the first non-whitespace content
                for (let sibling = current.firstChild; sibling; sibling = sibling.nextSibling) {
                    // Check if this sibling is or contains our text node
                    if (sibling === textNode) {
                        // Found ourselves - we're first
                        return true;
                    }
                    // Check if our text node is inside this sibling
                    if (sibling.nodeType === Node.ELEMENT_NODE && sibling.contains && sibling.contains(textNode)) {
                        // Our text is inside this sibling
                        // Check if any previous sibling has visible content
                        // (We already checked prev_siblings above, so if we got here, we're first)
                        return true;
                    }
                    // Check if this sibling has visible content before us
                    if (hasVisibleContent(sibling)) {
                        return false;
                    }
                }
                // We're the first non-whitespace content in this block element
                return true;
            } else if (current.parentElement) {
                current = current.parentElement;
            } else {
                break;
            }
        }
        
        return false;
    }
    
    /**
     * Extract all text nodes from the entire page
     * Returns array of text content and corresponding nodes
     */
    function extractAllTextNodes() {
        const textNodes = [];
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    // Skip if parent is in skip list
                    let parent = node.parentElement;
                    while (parent && parent !== document.body) {
                        if (CONFIG.skipSelectors.some(sel => {
                            try {
                                return parent.matches && parent.matches(sel);
                            } catch (e) {
                                return false;
                            }
                        })) {
                            return NodeFilter.FILTER_REJECT;
                        }
                        parent = parent.parentElement;
                    }
                    
                    // Skip if text is too short
                    const text = node.textContent.trim();
                    if (text.length < CONFIG.minTextLength) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );
        
        let node;
        while (node = walker.nextNode()) {
            // CRITICAL: Preserve original text content (including leading/trailing spaces)
            // This is important for maintaining spacing around hyperlinks and other inline elements
            const originalText = node.textContent;
            const trimmedText = originalText.trim();
            
            // Only process if trimmed text meets minimum length
            if (trimmedText.length >= CONFIG.minTextLength) {
                textNodes.push({
                    node: node,
                    text: trimmedText,  // Use trimmed text for encryption
                    originalText: originalText  // Preserve original for spacing
                });
            }
        }
        
        return textNodes;
    }
    
    // ============================================================================
    // FONT LOADING
    // ============================================================================
    
    let currentFontUrl = null;
    let fontLoadingPromise = null;
    
    /**
     * Load the custom encryption font
     * Always reloads if fontUrl changes to ensure we get the latest font
     */
    async function loadFont(fontUrl) {
        if (!fontUrl) {
            return false;
        }
        
        // If this is the same font URL and it's already loading, wait for it
        if (fontUrl === currentFontUrl && fontLoadingPromise) {
            return fontLoadingPromise;
        }
        
        // If font URL changed, remove old font and load new one
        if (currentFontUrl && fontUrl !== currentFontUrl) {
            // Remove old font from document.fonts
            try {
                const oldFonts = document.fonts.check(`12px ${CONFIG.fontName}`);
                // Delete all fonts with this name
                for (let i = document.fonts.length - 1; i >= 0; i--) {
                    const font = document.fonts[i];
                    if (font.family === CONFIG.fontName) {
                        document.fonts.delete(font);
                    }
                }
            } catch (e) {
                // Ignore errors when removing fonts
            }
            currentFontUrl = null;
            fontLoadingPromise = null;
        }
        
        // If already loaded with this URL, return immediately
        if (fontUrl === currentFontUrl) {
            return true;
        }
        
        fontLoadingPromise = (async () => {
            try {
                // Add cache-busting to font URL to prevent browser caching
                const cacheBuster = `?t=${Date.now()}`;
                const fontUrlWithCacheBust = fontUrl.includes('?') 
                    ? `${fontUrl}&t=${Date.now()}` 
                    : `${fontUrl}?t=${Date.now()}`;
                
                const font = new FontFace(CONFIG.fontName, `url(${fontUrlWithCacheBust})`, {
                    display: 'swap'
                });
                await font.load();
                document.fonts.add(font);
                currentFontUrl = fontUrl;
                return true;
            } catch (error) {
                console.error('Font loading failed:', error);
                currentFontUrl = null;
                fontLoadingPromise = null;
                return false;
            }
        })();
        
        return fontLoadingPromise;
    }
    
    // ============================================================================
    // API COMMUNICATION
    // ============================================================================
    
    /**
     * Encrypt all text from the page with a single API call
     */
    async function encryptPage() {
        try {
            // Extract all text nodes
            const textNodes = extractAllTextNodes();
            
            if (textNodes.length === 0) {
                console.log('No text nodes found to encrypt');
                return;
            }
            
            // Extract just the text content
            const texts = textNodes.map(tn => tn.text);
            
            // Call API once with all text
            // Only include secret_key if explicitly set (otherwise API uses server default)
            const requestBody = { texts: texts };
            if (CONFIG.secretKey !== null) {
                requestBody.secret_key = CONFIG.secretKey;
            }
            
            const response = await fetch(CONFIG.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({ error: response.statusText }));
                throw new Error(`API error: ${response.status} - ${error.error || response.statusText}`);
            }
            
            const data = await response.json();
            
            if (!data.encrypted_texts || !Array.isArray(data.encrypted_texts)) {
                throw new Error('Invalid API response: missing encrypted_texts array');
            }
            
            // DEBUG: Print mapping and font URL
            console.log('='.repeat(70));
            console.log('ENCRYPTION DEBUG INFO');
            console.log('='.repeat(70));
            console.log('Font URL:', data.font_url);
            console.log('Font Filename:', data.font_filename);
            console.log('Nonce:', data.nonce);
            console.log('Space Character (what space encrypts to):', JSON.stringify(data.space_char));
            
            if (data.upper_map && data.lower_map) {
                console.log('\nEncryption Mapping (original -> encrypted):');
                console.log('Upper map:', data.upper_map);
                console.log('Lower map:', data.lower_map);
                
                // Create reverse mapping (encrypted -> original) for font
                const fontMappingUpper = {};
                const fontMappingLower = {};
                for (const [orig, enc] of Object.entries(data.upper_map)) {
                    fontMappingUpper[enc] = orig;
                }
                for (const [orig, enc] of Object.entries(data.lower_map)) {
                    fontMappingLower[enc] = orig;
                }
                
                console.log('\nFont Mapping (encrypted -> original):');
                console.log('Upper font map:', fontMappingUpper);
                console.log('Lower font map:', fontMappingLower);
                
                // Check what space maps to in encryption
                if (data.lower_map[' '] !== undefined) {
                    const spaceEncryptsTo = data.lower_map[' '];
                    console.log(`\nSpace encrypts to: ${JSON.stringify(spaceEncryptsTo)}`);
                    
                    // Check what that character should display in font
                    if (fontMappingUpper[spaceEncryptsTo] !== undefined) {
                        console.log(`Font should display '${spaceEncryptsTo}' as: ${JSON.stringify(fontMappingUpper[spaceEncryptsTo])}`);
                    } else if (fontMappingLower[spaceEncryptsTo] !== undefined) {
                        console.log(`Font should display '${spaceEncryptsTo}' as: ${JSON.stringify(fontMappingLower[spaceEncryptsTo])}`);
                    } else {
                        console.log(`⚠️ WARNING: '${spaceEncryptsTo}' is not in font mapping!`);
                    }
                }
                
                // Check if actual space appears in encrypted text and what it should display
                const hasActualSpace = data.encrypted_texts.some(text => text && text.includes(' '));
                if (hasActualSpace) {
                    console.log('\n⚠️ Actual space character appears in encrypted text!');
                    if (fontMappingLower[' '] !== undefined) {
                        console.log(`Font should display actual space ' ' as: ${JSON.stringify(fontMappingLower[' '])}`);
                    } else {
                        console.log(`⚠️ WARNING: Actual space ' ' is not in font mapping!`);
                    }
                }
            }
            console.log('='.repeat(70));
            
            // Load font
            if (data.font_url) {
                console.log('Loading font from:', data.font_url);
                await loadFont(data.font_url);
            }
            
            // Get the character that space maps to (for word-breaking)
            const spaceChar = data.space_char;
            
            // Store decryption mappings for copy-paste functionality
            if (data.upper_map && data.lower_map && data.space_map) {
                storeDecryptionMappings(
                    data.upper_map,
                    data.lower_map,
                    data.space_map,
                    data.nonce,
                    CONFIG.secretKey
                );
            }
            
            // Replace all text nodes with encrypted versions
            textNodes.forEach((textNode, index) => {
                const encryptedText = data.encrypted_texts[index];
                if (encryptedText) {
                    // CRITICAL: Preserve leading and trailing spaces from original text
                    // This maintains spacing around hyperlinks and other inline elements
                    // EXCEPT: Strip leading spaces if this text node is at the start of a new line
                    // This prevents spaces from appearing at the beginning of lines
                    const originalText = textNode.originalText || textNode.text;
                    let leadingSpaces = originalText.match(/^\s*/)?.[0] || '';
                    const trailingSpaces = originalText.match(/\s*$/)?.[0] || '';
                    
                    // Strip leading spaces if at line start
                    if (isTextAtLineStart(textNode.node)) {
                        leadingSpaces = '';
                    }
                    
                    // CRITICAL: Replace actual space characters with non-breaking spaces
                    // This prevents the browser from treating them as line-break points
                    // The font will still render them as the correct glyph (e.g., 'J')
                    // Non-breaking space (U+00A0) has the same glyph mapping as regular space (U+0020)
                    // in our font, so it will display correctly
                    let processedText = encryptedText.replace(/\u0020/g, '\u00A0');  // Replace regular spaces with non-breaking spaces
                    
                    // CRITICAL: Split text at spaceChar and wrap each word in a span to allow breaking
                    // This allows CSS to break at word boundaries (where original spaces were) without using zero-width spaces
                    const parent = textNode.node.parentElement;
                    if (parent && spaceChar) {
                        // Split text at spaceChar (the character that original spaces encrypt to)
                        const escapedSpaceChar = spaceChar.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                        const parts = processedText.split(new RegExp(`(${escapedSpaceChar})`, 'g'));
                        
                        // Create a document fragment to hold the wrapped segments
                        const fragment = document.createDocumentFragment();
                        
                        // Add leading spaces as spaceChar characters (preserves spacing around links)
                        // Use spaceChar instead of actual spaces so they render correctly through the font
                        if (leadingSpaces) {
                            const leadingSpaceCount = leadingSpaces.length;
                            const leadingSpaceSpan = document.createElement('span');
                            leadingSpaceSpan.textContent = spaceChar.repeat(leadingSpaceCount);
                            leadingSpaceSpan.style.display = 'inline-block';
                            leadingSpaceSpan.style.whiteSpace = 'nowrap';
                            fragment.appendChild(leadingSpaceSpan);
                        }
                        
                        parts.forEach((part, partIndex) => {
                            if (part === '') return; // Skip empty parts
                            
                            if (part === spaceChar) {
                                // This is the spaceChar - wrap it in a span that allows breaking after it
                                const span = document.createElement('span');
                                span.textContent = part;
                                span.style.display = 'inline-block'; // Allow breaking between inline-block elements
                                span.style.whiteSpace = 'nowrap'; // Prevent breaking within the spaceChar
                                fragment.appendChild(span);
                            } else {
                                // This is a word segment - wrap it in a span that cannot break internally
                                const span = document.createElement('span');
                                span.textContent = part;
                                span.style.display = 'inline-block'; // Allow breaking between inline-block elements
                                span.style.whiteSpace = 'nowrap'; // CRITICAL: Prevent breaking within words
                                span.style.wordBreak = 'keep-all'; // Additional protection against breaking
                                fragment.appendChild(span);
                            }
                        });
                        
                        // Add trailing spaces as spaceChar characters (preserves spacing around links)
                        // Use spaceChar instead of actual spaces so they render correctly through the font
                        if (trailingSpaces) {
                            const trailingSpaceCount = trailingSpaces.length;
                            const trailingSpaceSpan = document.createElement('span');
                            trailingSpaceSpan.textContent = spaceChar.repeat(trailingSpaceCount);
                            trailingSpaceSpan.style.display = 'inline-block';
                            trailingSpaceSpan.style.whiteSpace = 'nowrap';
                            fragment.appendChild(trailingSpaceSpan);
                        }
                        
                        // CRITICAL: After creating all spans, check if the container will start on a new line.
                        // If so, remove all leading spaceChar ('O') spans to prevent spaces from appearing at the beginning of lines.
                        const containerWillStartLine = isTextAtLineStart(textNode.node);
                        if (fragment.firstChild && containerWillStartLine && spaceChar) {
                            // Keep removing 'O' (spaceChar) spans from the start until we hit a non-spaceChar span
                            while (fragment.firstChild) {
                                const firstChild = fragment.firstChild;
                                // Check if first child is a span containing only spaceChar characters
                                if (firstChild.nodeType === Node.ELEMENT_NODE && 
                                    firstChild.tagName === 'SPAN' && 
                                    firstChild.textContent) {
                                    const text = firstChild.textContent.trim();
                                    // Check if it's only spaceChar (remove all spaceChar and see if anything remains)
                                    const textWithoutSpaceChar = text.replace(new RegExp(spaceChar.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), '');
                                    if (textWithoutSpaceChar === '' && text.length > 0) {
                                        // First child is a leading space span - remove it
                                        fragment.removeChild(firstChild);
                                        continue; // Check next child
                                    }
                                    // Also check if it's exactly a single spaceChar
                                    if (text === spaceChar) {
                                        // Single spaceChar at start of line - remove it
                                        fragment.removeChild(firstChild);
                                        continue; // Check next child
                                    }
                                }
                                // If we get here, first child is not a spaceChar span, so stop
                                break;
                            }
                        }
                        
                        // Replace the original text node with the fragment
                        parent.insertBefore(fragment, textNode.node);
                        textNode.node.remove();
                        
                        // Apply font and rendering properties to parent element
                        parent.style.fontFamily = `${CONFIG.fontName}, sans-serif`;
                        parent.style.textRendering = 'optimizeLegibility';
                        parent.style.whiteSpace = 'normal'; // Allow breaking between inline-block children (spans)
                        // Allow breaking between inline-block elements
                        parent.style.wordBreak = 'normal';
                        parent.style.overflowWrap = 'normal';
                        parent.style.wordWrap = 'normal';
                        // Prevent text clipping at line breaks
                        parent.style.overflow = 'visible';
                        parent.style.textOverflow = 'clip';
                    }
                }
            });
            
            // Post-process: Remove leading 'O' (spaceChar) spans from containers that are first children of block elements
            // This catches cases where the container itself starts on a new line
            if (spaceChar) {
                const blockElements = ['DIV', 'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'UL', 'OL', 'LI', 
                                     'BLOCKQUOTE', 'PRE', 'SECTION', 'ARTICLE', 'HEADER', 'FOOTER', 
                                     'NAV', 'ASIDE', 'TABLE', 'TR', 'TD', 'TH', 'HR', 'FIGURE', 'FIGCAPTION', 'BODY',
                                     'MAIN', 'FORM', 'FIELDSET', 'DL', 'DT', 'DD'];
                
                // Find all containers (spans with white-space: normal)
                const containers = document.querySelectorAll('span[style*="white-space: normal"]');
                containers.forEach(container => {
                    const parent = container.parentElement;
                    if (parent && blockElements.includes(parent.tagName)) {
                        // Check if container is at start of line
                        let isAtLineStart = false;
                        
                        // Check if container is first child
                        if (parent.firstChild === container) {
                            isAtLineStart = true;
                        } else {
                            // Check previous siblings
                            let prev = container.previousSibling;
                            while (prev) {
                                if (prev.nodeType === Node.ELEMENT_NODE) {
                                    if (prev.tagName === 'BR' || blockElements.includes(prev.tagName)) {
                                        isAtLineStart = true;
                                        break;
                                    }
                                    if (prev.textContent.trim()) {
                                        break;
                                    }
                                } else if (prev.nodeType === Node.TEXT_NODE && prev.textContent.trim()) {
                                    break;
                                }
                                prev = prev.previousSibling;
                            }
                            
                            // If all previous siblings were whitespace and parent is block, we're at line start
                            if (!isAtLineStart) {
                                let prev = container.previousSibling;
                                let allPrevWhitespace = true;
                                while (prev) {
                                    if (prev.nodeType === Node.ELEMENT_NODE) {
                                        if (blockElements.includes(prev.tagName) || prev.tagName === 'BR') {
                                            allPrevWhitespace = false;
                                            break;
                                        }
                                        if (prev.textContent.trim()) {
                                            allPrevWhitespace = false;
                                            break;
                                        }
                                    } else if (prev.nodeType === Node.TEXT_NODE && prev.textContent.trim()) {
                                        allPrevWhitespace = false;
                                        break;
                                    }
                                    prev = prev.previousSibling;
                                }
                                if (allPrevWhitespace) {
                                    isAtLineStart = true;
                                }
                            }
                        }
                        
                        // If container is at line start, remove leading 'O' (spaceChar) spans
                        if (isAtLineStart && container.firstChild) {
                            // Keep removing 'O' spans from the start
                            while (container.firstChild) {
                                const firstChild = container.firstChild;
                                if (firstChild.nodeType === Node.ELEMENT_NODE && 
                                    firstChild.tagName === 'SPAN' && 
                                    firstChild.textContent) {
                                    const text = firstChild.textContent.trim();
                                    // Check if it's only spaceChar
                                    const textWithoutSpaceChar = text.replace(new RegExp(spaceChar.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), '');
                                    if (textWithoutSpaceChar === '' && text.length > 0) {
                                        container.removeChild(firstChild);
                                        continue;
                                    }
                                    if (text === spaceChar) {
                                        container.removeChild(firstChild);
                                        continue;
                                    }
                                }
                                // If we get here, first child is not a spaceChar span, so stop
                                break;
                            }
                        }
                    }
                });
            }
            
            console.log(`✅ Encrypted ${textNodes.length} text nodes on the page`);
            
        } catch (error) {
            console.error('Page encryption failed:', error);
        }
    }
    
    // ============================================================================
    // COPY-PASTE INTERCEPTION
    // ============================================================================
    
    /**
     * Intercept copy events and replace clipboard content with decrypted text
     * This allows users to copy-paste normally while scrapers see encrypted text
     */
    function setupCopyInterception() {
        document.addEventListener('copy', function(e) {
            // Only intercept if we have secret key and nonce for API calls
            const secretKey = mappingStore[KEY_STORE] || CONFIG.secretKey;
            const nonce = mappingStore[NONCE_STORE];
            
            if (!secretKey || !nonce) {
                return; // Let default copy behavior proceed
            }
            
            const selection = window.getSelection();
            if (!selection || selection.rangeCount === 0) {
                return; // No selection, let default behavior proceed
            }
            
            // Get selected text (this will be the encrypted text)
            const selectedText = selection.toString();
            
            if (!selectedText || selectedText.trim().length === 0) {
                return; // Empty selection, let default behavior proceed
            }
            
            // Prevent default copy behavior
            e.preventDefault();
            
            // Get API base URL from endpoint
            let apiBaseUrl = CONFIG.apiEndpoint;
            try {
                // Extract base URL from endpoint (e.g., /api/encrypt/page -> origin)
                const endpointUrl = new URL(apiBaseUrl, window.location.href);
                apiBaseUrl = endpointUrl.origin;
            } catch (e) {
                // If parsing fails, use current origin
                apiBaseUrl = window.location.origin;
            }
            
            // Normalize text (remove zero-width spaces and normalize non-breaking spaces)
            const textWithoutZWSP = selectedText.replace(/\u200B/g, '');
            const normalizedText = textWithoutZWSP.replace(/\u00A0/g, ' ');
            
            // Decrypt synchronously using XMLHttpRequest (required for clipboardData API)
            let decryptedText = selectedText; // Default to encrypted text if decryption fails
            
            try {
                const xhr = new XMLHttpRequest();
                const apiUrl = `${apiBaseUrl}/api/decrypt`;
                
                xhr.open('POST', apiUrl, false); // false = synchronous
                xhr.setRequestHeader('Content-Type', 'application/json');
                
                // Send request
                xhr.send(JSON.stringify({
                    encrypted: normalizedText,
                    secret_key: mappingStore[KEY_STORE] || CONFIG.secretKey,
                    nonce: mappingStore[NONCE_STORE]
                }));
                
                // Check response
                if (xhr.status === 200) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        decryptedText = data.decrypted || selectedText;
                    } catch (parseError) {
                        console.error('Failed to parse decryption response:', parseError);
                        decryptedText = selectedText;
                    }
                } else {
                    console.error('Decryption API returned status:', xhr.status);
                    decryptedText = selectedText;
                }
            } catch (error) {
                console.error('Decryption API call failed:', error);
                decryptedText = selectedText;
            }
            
            // Replace clipboard content with decrypted text
            e.clipboardData.setData('text/plain', decryptedText);
            
            // Optional: Log for debugging (remove in production)
            if (CONFIG.debug) {
                console.log('Copy intercepted: decrypted text for clipboard');
            }
        }, true); // Use capture phase to intercept early
    }
    
    // ============================================================================
    // CUSTOM SEARCH FUNCTIONALITY
    // ============================================================================
    
    // Search state (private closure)
    let searchState = {
        overlay: null,
        input: null,
        matchCounter: null,
        prevButton: null,
        nextButton: null,
        closeButton: null,
        currentMatches: [],
        currentMatchIndex: -1,
        highlightElements: []
    };
    
    /**
     * Expand ligatures in text (same as server-side)
     */
    const LIGATURES = {"\ufb00":"ff","\ufb01":"fi","\ufb02":"fl","\ufb03":"ffi","\ufb04":"ffl"};
    function expandLigatures(text) {
        return text.split('').map(ch => LIGATURES[ch] || ch).join('');
    }
    
    /**
     * Encrypt search query using the API (no mappings exposed in HTML)
     */
    async function encryptSearchQuery(query) {
        if (!query || query.length === 0) {
            return '';
        }
        
        const secretKey = mappingStore[KEY_STORE] || CONFIG.secretKey;
        const nonce = mappingStore[NONCE_STORE];
        
        if (!secretKey || !nonce) {
            return query; // Return as-is if config is missing
        }
        
        // Get API base URL from endpoint
        let apiBaseUrl = CONFIG.apiEndpoint;
        try {
            // Extract base URL from endpoint (e.g., /api/encrypt/page -> origin)
            const endpointUrl = new URL(apiBaseUrl, window.location.href);
            apiBaseUrl = endpointUrl.origin;
        } catch (e) {
            // If parsing fails, use current origin
            apiBaseUrl = window.location.origin;
        }
        
        try {
            const response = await fetch(`${apiBaseUrl}/api/encrypt/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: query,
                    secret_key: secretKey,
                    nonce: nonce
                })
            });
            
            if (!response.ok) {
                console.warn('Encrypt query API call failed:', response.status);
                return query; // Return original if API fails
            }
            
            const data = await response.json();
            return data.encrypted || query;
        } catch (error) {
            console.warn('Error calling encrypt query API:', error);
            return query; // Return original if API call fails
        }
    }
    
    /**
     * Extract all text nodes for search
     * Handles span-wrapped text by getting textContent from parent elements
     */
    function extractTextNodesForSearch() {
        const textNodes = [];
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    // Skip if parent is in skip list
                    let parent = node.parentElement;
                    while (parent && parent !== document.body) {
                        if (CONFIG.skipSelectors.some(sel => {
                            try {
                                return parent.matches && parent.matches(sel);
                            } catch (e) {
                                return false;
                            }
                        })) {
                            return NodeFilter.FILTER_REJECT;
                        }
                        parent = parent.parentElement;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );
        
        // Collect all text nodes
        const rawNodes = [];
        let node;
        while (node = walker.nextNode()) {
            rawNodes.push(node);
        }
        
        // Group consecutive text nodes that belong to the same parent element
        // This handles the case where text is split across multiple spans
        const processedParents = new Set();
        
        rawNodes.forEach(node => {
            // Get the parent element that contains the encrypted text
            let parent = node.parentElement;
            while (parent && parent !== document.body) {
                // Check if this parent has the encrypted font applied
                const fontFamily = window.getComputedStyle(parent).fontFamily;
                if (fontFamily.includes(CONFIG.fontName)) {
                    // This is an encrypted text container
                    if (!processedParents.has(parent)) {
                        processedParents.add(parent);
                        
                        // Get all text content from this parent (includes all child spans)
                        const text = parent.textContent;
                        // Remove zero-width spaces and normalize non-breaking spaces for search
                        const normalizedText = text.replace(/\u200B/g, '').replace(/\u00A0/g, ' ');
                        
                        if (normalizedText.trim().length > 0) {
                            // Store the first text node as reference, but use parent's textContent
                            textNodes.push({
                                node: node, // Use first text node as reference
                                parent: parent, // Store parent for highlighting
                                text: normalizedText
                            });
                        }
                    }
                    break;
                }
                parent = parent.parentElement;
            }
        });
        
        return textNodes;
    }
    
    /**
     * Search DOM for encrypted query
     * Returns array of match objects: {node, parent, startIndex, endIndex, text}
     */
    function searchEncryptedDOM(encryptedQuery) {
        if (!encryptedQuery || encryptedQuery.length === 0) {
            return [];
        }
        
        const matches = [];
        const textNodes = extractTextNodesForSearch();
        
        // Normalize the query (remove zero-width spaces, normalize non-breaking spaces)
        const normalizedQuery = encryptedQuery.replace(/\u200B/g, '').replace(/\u00A0/g, ' ');
        
        for (const textNode of textNodes) {
            const text = textNode.text;
            let startIndex = 0;
            
            // Search for all occurrences
            while (true) {
                const index = text.indexOf(normalizedQuery, startIndex);
                if (index === -1) {
                    break;
                }
                
                matches.push({
                    node: textNode.node,
                    parent: textNode.parent || textNode.node.parentElement,
                    startIndex: index,
                    endIndex: index + normalizedQuery.length,
                    text: normalizedQuery
                });
                
                startIndex = index + 1;
            }
        }
        
        return matches;
    }
    
    /**
     * Clear all search highlights
     */
    function clearHighlights() {
        searchState.highlightElements.forEach(el => {
            if (el.parentNode) {
                const parent = el.parentNode;
                parent.replaceChild(document.createTextNode(el.textContent), el);
                parent.normalize();
            }
        });
        searchState.highlightElements = [];
    }
    
    /**
     * Highlight matches in the DOM
     * Uses parent element and Range API for reliable highlighting across span boundaries
     */
    function highlightMatches(matches, currentIndex) {
        // Clear previous highlights first
        clearHighlights();
        
        if (matches.length === 0) {
            return;
        }
        
        // Group matches by parent element
        const matchesByParent = new Map();
        matches.forEach((match, index) => {
            const parent = match.parent;
            if (!parent) return;
            
            if (!matchesByParent.has(parent)) {
                matchesByParent.set(parent, []);
            }
            matchesByParent.get(parent).push({...match, matchIndex: index});
        });
        
        // Process each parent element
        matchesByParent.forEach((parentMatches, parent) => {
            if (!parent || !parent.parentNode) {
                return;
            }
            
            // Get all text nodes within this parent
            const walker = document.createTreeWalker(
                parent,
                NodeFilter.SHOW_TEXT,
                null
            );
            
            const textNodes = [];
            let node;
            while (node = walker.nextNode()) {
                textNodes.push(node);
            }
            
            if (textNodes.length === 0) {
                return;
            }
            
            // Build a map of character positions to text nodes
            let charOffset = 0;
            const charToNode = [];
            textNodes.forEach(textNode => {
                const text = textNode.textContent.replace(/\u200B/g, '').replace(/\u00A0/g, ' ');
                for (let i = 0; i < text.length; i++) {
                    charToNode.push({
                        node: textNode,
                        offset: i,
                        globalOffset: charOffset + i
                    });
                }
                charOffset += text.length;
            });
            
            // Process matches in reverse order (end to start) to preserve indices
            parentMatches.sort((a, b) => b.startIndex - a.startIndex);
            
            parentMatches.forEach(match => {
                try {
                    const startChar = charToNode[match.startIndex];
                    const endChar = charToNode[match.endIndex - 1];
                    
                    if (!startChar || !endChar) {
                        return;
                    }
                    
                    // Create range
                    const range = document.createRange();
                    range.setStart(startChar.node, startChar.offset);
                    range.setEnd(endChar.node, endChar.offset + 1);
                    
                    // Create highlight element
                    const highlight = document.createElement('mark');
                    highlight.className = 'encrypted-search-highlight';
                    if (match.matchIndex === currentIndex) {
                        highlight.className += ' encrypted-search-current';
                    }
                    highlight.style.backgroundColor = match.matchIndex === currentIndex 
                        ? '#ffeb3b' 
                        : '#fff59d';
                    highlight.style.padding = '0';
                    highlight.style.borderRadius = '2px';
                    
                    // Surround contents
                    try {
                        range.surroundContents(highlight);
                        searchState.highlightElements.push(highlight);
                    } catch (e) {
                        // If surroundContents fails, extract and insert
                        const contents = range.extractContents();
                        highlight.appendChild(contents);
                        range.insertNode(highlight);
                        searchState.highlightElements.push(highlight);
                    }
                } catch (e) {
                    console.warn('Error highlighting match:', e);
                }
            });
        });
        
        // Scroll current match into view
        if (currentIndex >= 0 && currentIndex < searchState.highlightElements.length) {
            const highlight = searchState.highlightElements[currentIndex];
            if (highlight && highlight.parentNode) {
                highlight.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }
    
    /**
     * Navigate to next/previous match
     */
    function navigateToMatch(direction) {
        const matches = searchState.currentMatches;
        if (matches.length === 0) {
            return;
        }
        
        if (direction === 'next') {
            searchState.currentMatchIndex = (searchState.currentMatchIndex + 1) % matches.length;
        } else if (direction === 'prev') {
            searchState.currentMatchIndex = searchState.currentMatchIndex <= 0 
                ? matches.length - 1 
                : searchState.currentMatchIndex - 1;
        }
        
        highlightMatches(matches, searchState.currentMatchIndex);
        updateMatchCounter();
    }
    
    /**
     * Update match counter display
     */
    function updateMatchCounter() {
        const count = searchState.currentMatches.length;
        const index = searchState.currentMatchIndex;
        
        if (count === 0) {
            searchState.matchCounter.textContent = 'No matches';
        } else {
            searchState.matchCounter.textContent = `${index + 1} of ${count}`;
        }
    }
    
    /**
     * Handle search input
     */
    async function handleSearchInput(event) {
        const query = event.target.value;
        
        if (!query || query.trim().length === 0) {
            clearHighlights();
            searchState.currentMatches = [];
            searchState.currentMatchIndex = -1;
            updateMatchCounter();
            return;
        }
        
        // Encrypt the query
        const encryptedQuery = await encryptSearchQuery(query);
        
        // Search DOM
        const matches = searchEncryptedDOM(encryptedQuery);
        searchState.currentMatches = matches;
        
        if (matches.length > 0) {
            searchState.currentMatchIndex = 0;
            highlightMatches(matches, 0);
        } else {
            searchState.currentMatchIndex = -1;
            clearHighlights();
        }
        
        updateMatchCounter();
    }
    
    /**
     * Create search overlay UI
     */
    function createSearchOverlay() {
        // Create overlay container
        const overlay = document.createElement('div');
        overlay.id = 'encrypted-search-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            border: 1px solid #ccc;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            padding: 8px;
            z-index: 10000;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 14px;
            display: none;
        `;
        
        // Create input container
        const inputContainer = document.createElement('div');
        inputContainer.style.cssText = 'display: flex; align-items: center; gap: 8px;';
        
        // Create search input
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'Search...';
        input.style.cssText = `
            border: 1px solid #ccc;
            border-radius: 2px;
            padding: 4px 8px;
            font-size: 14px;
            width: 200px;
            outline: none;
        `;
        input.addEventListener('input', handleSearchInput);
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                navigateToMatch('next');
            } else if (e.key === 'Enter' && e.shiftKey) {
                e.preventDefault();
                navigateToMatch('prev');
            } else if (e.key === 'Escape') {
                e.preventDefault();
                hideSearchOverlay();
            }
        });
        
        // Create match counter
        const matchCounter = document.createElement('span');
        matchCounter.style.cssText = 'color: #666; font-size: 12px; min-width: 60px; text-align: center;';
        matchCounter.textContent = 'No matches';
        
        // Create navigation buttons
        const prevButton = document.createElement('button');
        prevButton.textContent = '↑';
        prevButton.title = 'Previous (Shift+Enter)';
        prevButton.style.cssText = `
            border: 1px solid #ccc;
            background: white;
            border-radius: 2px;
            padding: 2px 8px;
            cursor: pointer;
            font-size: 12px;
        `;
        prevButton.addEventListener('click', () => navigateToMatch('prev'));
        
        const nextButton = document.createElement('button');
        nextButton.textContent = '↓';
        nextButton.title = 'Next (Enter)';
        nextButton.style.cssText = prevButton.style.cssText;
        nextButton.addEventListener('click', () => navigateToMatch('next'));
        
        // Create close button
        const closeButton = document.createElement('button');
        closeButton.textContent = '×';
        closeButton.title = 'Close (Esc)';
        closeButton.style.cssText = `
            border: none;
            background: transparent;
            font-size: 18px;
            cursor: pointer;
            padding: 0 4px;
            line-height: 1;
            color: #666;
        `;
        closeButton.addEventListener('click', hideSearchOverlay);
        
        // Assemble overlay
        inputContainer.appendChild(input);
        inputContainer.appendChild(matchCounter);
        inputContainer.appendChild(prevButton);
        inputContainer.appendChild(nextButton);
        inputContainer.appendChild(closeButton);
        overlay.appendChild(inputContainer);
        
        // Store references
        searchState.overlay = overlay;
        searchState.input = input;
        searchState.matchCounter = matchCounter;
        searchState.prevButton = prevButton;
        searchState.nextButton = nextButton;
        searchState.closeButton = closeButton;
        
        return overlay;
    }
    
    /**
     * Show search overlay
     */
    function showSearchOverlay() {
        if (!searchState.overlay) {
            const overlay = createSearchOverlay();
            document.body.appendChild(overlay);
        }
        
        searchState.overlay.style.display = 'block';
        searchState.input.focus();
        searchState.input.select();
    }
    
    /**
     * Hide search overlay
     */
    function hideSearchOverlay() {
        if (searchState.overlay) {
            searchState.overlay.style.display = 'none';
            searchState.input.value = '';
            clearHighlights();
            searchState.currentMatches = [];
            searchState.currentMatchIndex = -1;
        }
    }
    
    /**
     * Setup Ctrl+F / Cmd+F interception
     */
    function setupSearchInterception() {
        document.addEventListener('keydown', function(e) {
            // Check for Ctrl+F (Windows/Linux) or Cmd+F (Mac)
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                e.stopPropagation();
                showSearchOverlay();
            }
        }, true); // Use capture phase to intercept early
    }
    
    // ============================================================================
    // INITIALIZATION
    // ============================================================================
    
    /**
     * Initialize encryption when DOM is ready
     */
    function init() {
        // Setup copy interception immediately (before encryption)
        setupCopyInterception();
        
        // Setup search interception
        setupSearchInterception();
        
        // Wait a bit for page to fully load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                setTimeout(encryptPage, 100);
            });
        } else {
            // DOM already loaded
            setTimeout(encryptPage, 100);
        }
    }
    
    // Start encryption
    init();
    
    // Expose manual encryption function
    if (typeof window !== 'undefined') {
        window.encryptPage = encryptPage;
    }
    
})();

