/**
 * Decryption Interceptor for Server-Side Encrypted Pages
 * Provides copy-paste interception and search functionality for pages encrypted server-side
 * 
 * Requires window.encryptionConfig to be set before this script loads:
 * window.encryptionConfig = {
 *     secretKey: 29202393,
 *     nonce: 462508,
 *     apiBaseUrl: 'http://localhost:5001'
 * };
 */
(function() {
    'use strict';
    
    // Get encryption config from window (must be set before this script loads)
    const encryptionConfig = window.encryptionConfig || {};
    
    /**
     * Decrypt text using the decryption API
     * Handles zero-width spaces, non-breaking spaces, and special characters
     */
    async function decryptText(encryptedText) {
        if (!encryptionConfig.secretKey || !encryptionConfig.nonce) {
            return encryptedText;
        }
        
        // Remove zero-width spaces (U+200B) that were inserted for word-breaking
        const textWithoutZWSP = encryptedText.replace(/\u200B/g, '');
        
        // Replace non-breaking spaces (U+00A0) with regular spaces for decryption
        // The font maps both regular spaces and non-breaking spaces to the same glyph
        const normalizedText = textWithoutZWSP.replace(/\u00A0/g, ' ');
        
        // Call the decryption API
        try {
            const response = await fetch(`${encryptionConfig.apiBaseUrl}/api/decrypt`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    encrypted: normalizedText,
                    secret_key: encryptionConfig.secretKey,
                    nonce: encryptionConfig.nonce
                })
            });
            
            if (!response.ok) {
                console.warn('Decryption API call failed:', response.status);
                return encryptedText; // Return original if API fails
            }
            
            const data = await response.json();
            return data.decrypted || encryptedText;
        } catch (error) {
            console.warn('Error calling decryption API:', error);
            return encryptedText; // Return original if API call fails
        }
    }
    
    /**
     * Intercept copy events and replace clipboard content with decrypted text
     * This allows users to copy-paste normally while scrapers see encrypted text
     * Note: Uses synchronous XMLHttpRequest because clipboardData API requires synchronous access
     */
    function setupCopyInterception() {
        document.addEventListener('copy', function(e) {
            // Only intercept if we have encryption config
            if (!encryptionConfig.secretKey || !encryptionConfig.nonce) {
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
            
            // Decrypt synchronously using XMLHttpRequest (required for clipboardData API)
            // Note: Synchronous XHR is deprecated but necessary here for clipboard operations
            // Modern browsers may block synchronous XHR for cross-origin requests
            let decryptedText = selectedText; // Default to encrypted text if decryption fails
            
            try {
                // Normalize text (remove zero-width spaces and normalize non-breaking spaces)
                const textWithoutZWSP = selectedText.replace(/\u200B/g, '');
                const normalizedText = textWithoutZWSP.replace(/\u00A0/g, ' ');
                
                // Make synchronous API call
                const xhr = new XMLHttpRequest();
                const apiUrl = `${encryptionConfig.apiBaseUrl}/api/decrypt`;
                
                // Check if we're on the same origin (synchronous XHR works better on same origin)
                const isSameOrigin = new URL(apiUrl, window.location.href).origin === window.location.origin;
                
                if (!isSameOrigin) {
                    console.warn('Cross-origin synchronous XHR may be blocked by browser. API URL:', apiUrl);
                }
                
                xhr.open('POST', apiUrl, false); // false = synchronous
                xhr.setRequestHeader('Content-Type', 'application/json');
                
                // Send request
                xhr.send(JSON.stringify({
                    encrypted: normalizedText,
                    secret_key: encryptionConfig.secretKey,
                    nonce: encryptionConfig.nonce
                }));
                
                // Check response
                if (xhr.status === 200) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        decryptedText = data.decrypted || selectedText;
                    } catch (parseError) {
                        console.error('Failed to parse decryption response:', parseError, 'Response:', xhr.responseText);
                        decryptedText = selectedText;
                    }
                } else {
                    console.error('Decryption API returned status:', xhr.status, xhr.statusText, 'Response:', xhr.responseText);
                    decryptedText = selectedText;
                }
            } catch (error) {
                console.error('Decryption API call failed:', error);
                console.error('This may be due to:', {
                    'Synchronous XHR blocked': 'Modern browsers block synchronous XHR for cross-origin requests',
                    'CORS issue': 'Check CORS configuration on the API server',
                    'Network error': 'Check if API is accessible at: ' + encryptionConfig.apiBaseUrl,
                    'Error details': error.message
                });
                // If decryption fails, use encrypted text (better than nothing)
                decryptedText = selectedText;
            }
            
            // Set clipboard data with decrypted text
            e.clipboardData.setData('text/plain', decryptedText);
        }, true); // Use capture phase to intercept early
    }
    
    // Setup copy interception immediately (before DOM is ready)
    // This ensures it's set up before any copy events can occur
    setupCopyInterception();
    
    // Also set up on DOMContentLoaded as a fallback
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupCopyInterception);
    }
    
    // ============================================================================
    // SEARCH FUNCTIONALITY
    // ============================================================================
    
    // Search state
    const searchState = {
        overlay: null,
        input: null,
        matchCounter: null,
        prevButton: null,
        nextButton: null,
        closeButton: null,
        currentMatches: [],
        currentMatchIndex: -1,
        highlightElements: [],
        lastOriginalQuery: '' // Store original query for case-insensitive search
    };
    
    // Ligatures mapping
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
        
        if (!encryptionConfig.secretKey || !encryptionConfig.nonce) {
            return query; // Return as-is if config is missing
        }
        
        try {
            const response = await fetch(`${encryptionConfig.apiBaseUrl}/api/encrypt/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: query,
                    secret_key: encryptionConfig.secretKey,
                    nonce: encryptionConfig.nonce
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
    
    function isElementVisible(element) {
        if (!element || element.nodeType !== Node.ELEMENT_NODE) {
            return false;
        }
        
        // Check computed style
        const style = window.getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
            return false;
        }
        
        // Check if element has zero dimensions
        const rect = element.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) {
            // Might be a line break or whitespace-only element, check if it has visible children
            const children = Array.from(element.children);
            if (children.length > 0) {
                // Check if any child is visible
                return children.some(child => isElementVisible(child));
            }
            // If no children and zero size, it's likely not visible
            return false;
        }
        
        return true;
    }
    
    function extractTextNodesForSearch() {
        const textNodes = [];
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    let parent = node.parentElement;
                    while (parent && parent !== document.body) {
                        const tagName = parent.tagName ? parent.tagName.toLowerCase() : '';
                        // Skip hidden elements
                        if (['script', 'style', 'noscript', 'meta', 'title', 'head'].includes(tagName)) {
                            return NodeFilter.FILTER_REJECT;
                        }
                        // Check if parent is visible
                        if (!isElementVisible(parent)) {
                            return NodeFilter.FILTER_REJECT;
                        }
                        parent = parent.parentElement;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );
        
        const rawNodes = [];
        let node;
        while (node = walker.nextNode()) {
            rawNodes.push(node);
        }
        
        const processedParents = new Set();
        rawNodes.forEach(node => {
            let parent = node.parentElement;
            while (parent && parent !== document.body) {
                const fontFamily = window.getComputedStyle(parent).fontFamily;
                if (fontFamily.includes('EncryptedFont')) {
                    // Only process if parent is visible
                    if (!isElementVisible(parent)) {
                        break;
                    }
                    
                    if (!processedParents.has(parent)) {
                        processedParents.add(parent);
                        const text = parent.textContent;
                        const normalizedText = text.replace(/\u200B/g, '').replace(/\u00A0/g, ' ');
                        if (normalizedText.trim().length > 0) {
                            textNodes.push({ node: node, parent: parent, text: normalizedText });
                        }
                    }
                    break;
                }
                parent = parent.parentElement;
            }
        });
        
        return textNodes;
    }
    
    async function searchEncryptedDOM(encryptedQuery) {
        if (!encryptedQuery || encryptedQuery.length === 0) {
            return [];
        }
        
        const matches = [];
        const textNodes = extractTextNodesForSearch();
        const normalizedQuery = encryptedQuery.replace(/\u200B/g, '').replace(/\u00A0/g, ' ');
        
        // For case-insensitive search, encrypt common case variations of the original query
        const originalQuery = searchState.lastOriginalQuery || '';
        const queriesToSearch = [normalizedQuery]; // Always include the query as-is
        
        if (originalQuery) {
            // Encrypt lowercase version
            const lowerEncrypted = await encryptSearchQuery(originalQuery.toLowerCase());
            if (lowerEncrypted && lowerEncrypted !== normalizedQuery) {
                queriesToSearch.push(lowerEncrypted.replace(/\u200B/g, '').replace(/\u00A0/g, ' '));
            }
            
            // Encrypt uppercase version
            const upperEncrypted = await encryptSearchQuery(originalQuery.toUpperCase());
            if (upperEncrypted && upperEncrypted !== normalizedQuery) {
                queriesToSearch.push(upperEncrypted.replace(/\u200B/g, '').replace(/\u00A0/g, ' '));
            }
            
            // Encrypt title case (first letter uppercase, rest lowercase)
            if (originalQuery.length > 0) {
                const titleCase = originalQuery[0].toUpperCase() + originalQuery.slice(1).toLowerCase();
                const titleEncrypted = await encryptSearchQuery(titleCase);
                if (titleEncrypted && titleEncrypted !== normalizedQuery) {
                    queriesToSearch.push(titleEncrypted.replace(/\u200B/g, '').replace(/\u00A0/g, ' '));
                }
            }
        }
        
        // Remove duplicates
        const uniqueQueries = [...new Set(queriesToSearch)];
        
        for (const textNode of textNodes) {
            const text = textNode.text;
            
            // Search for each encrypted query variation
            for (const queryToSearch of uniqueQueries) {
                let startIndex = 0;
                while (true) {
                    const index = text.indexOf(queryToSearch, startIndex);
                    if (index === -1) break;
                    
                    // Check if we already have this match (avoid duplicates)
                    const isDuplicate = matches.some(m => 
                        m.parent === textNode.parent && 
                        m.startIndex === index && 
                        m.endIndex === index + queryToSearch.length
                    );
                    
                    if (!isDuplicate) {
                        matches.push({
                            node: textNode.node,
                            parent: textNode.parent,
                            startIndex: index,
                            endIndex: index + queryToSearch.length,
                            text: queryToSearch
                        });
                    }
                    
                    startIndex = index + 1;
                }
            }
        }
        
        return matches;
    }
    
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
    
    function highlightMatches(matches, currentIndex) {
        clearHighlights();
        if (matches.length === 0) return;
        
        const matchesByParent = new Map();
        matches.forEach((match, index) => {
            const parent = match.parent;
            if (!parent) return;
            if (!matchesByParent.has(parent)) {
                matchesByParent.set(parent, []);
            }
            matchesByParent.get(parent).push({...match, matchIndex: index});
        });
        
        matchesByParent.forEach((parentMatches, parent) => {
            if (!parent || !parent.parentNode) return;
            
            const walker = document.createTreeWalker(parent, NodeFilter.SHOW_TEXT, null);
            const textNodes = [];
            let node;
            while (node = walker.nextNode()) {
                textNodes.push(node);
            }
            if (textNodes.length === 0) return;
            
            let charOffset = 0;
            const charToNode = [];
            textNodes.forEach(textNode => {
                const text = textNode.textContent.replace(/\u200B/g, '').replace(/\u00A0/g, ' ');
                for (let i = 0; i < text.length; i++) {
                    charToNode.push({ node: textNode, offset: i, globalOffset: charOffset + i });
                }
                charOffset += text.length;
            });
            
            parentMatches.sort((a, b) => b.startIndex - a.startIndex);
            parentMatches.forEach(match => {
                try {
                    const startChar = charToNode[match.startIndex];
                    const endChar = charToNode[match.endIndex - 1];
                    if (!startChar || !endChar) return;
                    
                    const range = document.createRange();
                    range.setStart(startChar.node, startChar.offset);
                    range.setEnd(endChar.node, endChar.offset + 1);
                    
                    const highlight = document.createElement('mark');
                    highlight.className = 'encrypted-search-highlight';
                    if (match.matchIndex === currentIndex) {
                        highlight.className += ' encrypted-search-current';
                    }
                    highlight.style.backgroundColor = match.matchIndex === currentIndex ? '#ffeb3b' : '#fff59d';
                    highlight.style.padding = '0';
                    highlight.style.borderRadius = '2px';
                    
                    try {
                        range.surroundContents(highlight);
                        searchState.highlightElements.push(highlight);
                    } catch (e) {
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
        
        if (currentIndex >= 0 && currentIndex < searchState.highlightElements.length) {
            const highlight = searchState.highlightElements[currentIndex];
            if (highlight && highlight.parentNode) {
                highlight.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }
    
    function navigateToMatch(direction) {
        const matches = searchState.currentMatches;
        if (matches.length === 0) return;
        
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
    
    function updateMatchCounter() {
        const count = searchState.currentMatches.length;
        const index = searchState.currentMatchIndex;
        if (count === 0) {
            searchState.matchCounter.textContent = 'No matches';
        } else {
            searchState.matchCounter.textContent = `${index + 1} of ${count}`;
        }
    }
    
    async function handleSearchInput(event) {
        const query = event.target.value;
        // Store original query for case-insensitive search
        searchState.lastOriginalQuery = query;
        
        if (!query || query.trim().length === 0) {
            clearHighlights();
            searchState.currentMatches = [];
            searchState.currentMatchIndex = -1;
            updateMatchCounter();
            return;
        }
        
        // Encrypt the query as-is (for display/search purposes)
        const encryptedQuery = await encryptSearchQuery(query);
        // The searchEncryptedDOM function will handle case-insensitive matching
        const matches = await searchEncryptedDOM(encryptedQuery);
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
    
    function createSearchOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'encrypted-search-overlay';
        overlay.style.cssText = `position: fixed; top: 20px; right: 20px; background: white; border: 1px solid #ccc; border-radius: 4px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); padding: 8px; z-index: 10000; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; font-size: 14px; display: none;`;
        
        const inputContainer = document.createElement('div');
        inputContainer.style.cssText = 'display: flex; align-items: center; gap: 8px;';
        
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'Search...';
        input.style.cssText = `border: 1px solid #ccc; border-radius: 2px; padding: 4px 8px; font-size: 14px; width: 200px; outline: none; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;`;
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
        
        const matchCounter = document.createElement('span');
        matchCounter.style.cssText = 'color: #666; font-size: 12px; min-width: 60px; text-align: center; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;';
        matchCounter.textContent = 'No matches';
        
        const prevButton = document.createElement('button');
        prevButton.textContent = '↑';
        prevButton.title = 'Previous (Shift+Enter)';
        prevButton.style.cssText = `border: 1px solid #ccc; background: white; border-radius: 2px; padding: 2px 8px; cursor: pointer; font-size: 12px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;`;
        prevButton.addEventListener('click', () => navigateToMatch('prev'));
        
        const nextButton = document.createElement('button');
        nextButton.textContent = '↓';
        nextButton.title = 'Next (Enter)';
        nextButton.style.cssText = prevButton.style.cssText;
        nextButton.addEventListener('click', () => navigateToMatch('next'));
        
        const closeButton = document.createElement('button');
        closeButton.textContent = '×';
        closeButton.title = 'Close (Esc)';
        closeButton.style.cssText = `border: none; background: transparent; font-size: 18px; cursor: pointer; padding: 0 4px; line-height: 1; color: #666; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;`;
        closeButton.addEventListener('click', hideSearchOverlay);
        
        inputContainer.appendChild(input);
        inputContainer.appendChild(matchCounter);
        inputContainer.appendChild(prevButton);
        inputContainer.appendChild(nextButton);
        inputContainer.appendChild(closeButton);
        overlay.appendChild(inputContainer);
        
        searchState.overlay = overlay;
        searchState.input = input;
        searchState.matchCounter = matchCounter;
        searchState.prevButton = prevButton;
        searchState.nextButton = nextButton;
        searchState.closeButton = closeButton;
        
        return overlay;
    }
    
    function showSearchOverlay() {
        if (!searchState.overlay) {
            const overlay = createSearchOverlay();
            document.body.appendChild(overlay);
        }
        searchState.overlay.style.display = 'block';
        searchState.input.focus();
        searchState.input.select();
    }
    
    function hideSearchOverlay() {
        if (searchState.overlay) {
            searchState.overlay.style.display = 'none';
            searchState.input.value = '';
            clearHighlights();
            searchState.currentMatches = [];
            searchState.currentMatchIndex = -1;
        }
    }
    
    function setupSearchInterception() {
        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                e.stopPropagation();
                showSearchOverlay();
            }
        }, true);
    }
    
    // Setup search interception immediately
    setupSearchInterception();
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupSearchInterception);
    }
})();

