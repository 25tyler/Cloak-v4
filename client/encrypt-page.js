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
            'head'
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
    // TEXT EXTRACTION
    // ============================================================================
    
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
            const text = node.textContent.trim();
            if (text.length >= CONFIG.minTextLength) {
                textNodes.push({
                    node: node,
                    text: text
                });
            }
        }
        
        return textNodes;
    }
    
    // ============================================================================
    // FONT LOADING
    // ============================================================================
    
    let fontLoaded = false;
    let fontLoadingPromise = null;
    
    /**
     * Load the custom encryption font
     */
    async function loadFont(fontUrl) {
        if (fontLoaded && fontUrl) {
            return true;
        }
        
        if (fontLoadingPromise) {
            return fontLoadingPromise;
        }
        
        if (!fontUrl) {
            return false;
        }
        
        fontLoadingPromise = (async () => {
            try {
                const font = new FontFace(CONFIG.fontName, `url(${fontUrl})`, {
                    display: 'swap'
                });
                await font.load();
                document.fonts.add(font);
                fontLoaded = true;
                return true;
            } catch (error) {
                console.error('Font loading failed:', error);
                fontLoaded = false;
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
            
            // Load font
            if (data.font_url) {
                await loadFont(data.font_url);
            }
            
            // Replace all text nodes with encrypted versions
            textNodes.forEach((textNode, index) => {
                const encryptedText = data.encrypted_texts[index];
                if (encryptedText) {
                    // Replace text content
                    textNode.node.textContent = encryptedText;
                    
                    // Apply font and rendering properties to parent element
                    const parent = textNode.node.parentElement;
                    if (parent) {
                        parent.style.fontFamily = `${CONFIG.fontName}, sans-serif`;
                        parent.style.textRendering = 'optimizeLegibility';
                        parent.style.overflowWrap = 'break-word';
                        parent.style.wordWrap = 'break-word';
                        // Prevent text clipping at line breaks
                        parent.style.overflow = 'visible';
                        parent.style.textOverflow = 'clip';
                    }
                }
            });
            
            console.log(`✅ Encrypted ${textNodes.length} text nodes on the page`);
            
        } catch (error) {
            console.error('Page encryption failed:', error);
        }
    }
    
    // ============================================================================
    // INITIALIZATION
    // ============================================================================
    
    /**
     * Initialize encryption when DOM is ready
     */
    function init() {
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

