/**
 * Article Encryption Client Script
 * Automatically encrypts all articles on news websites
 * 
 * Usage: Add this script to your news website:
 * <script src="https://your-cdn.com/encrypt-articles.js" async></script>
 */
(function() {
    'use strict';
    
    // ============================================================================
    // CONFIGURATION
    // ============================================================================
    const CONFIG = {
        // Your API endpoint URL
        apiEndpoint: 'https://cloak-v3-707b7c7f67b3.herokuapp.com/api/encrypt',
        
        // Batch endpoint (more efficient for multiple articles)
        batchEndpoint: 'https://cloak-v3-707b7c7f67b3.herokuapp.com/api/encrypt/batch',
        
        // Use batch API (recommended for high-traffic sites)
        useBatch: true,
        
        // Batch size (how many articles to encrypt at once)
        batchSize: 10,
        
        // Font name for encrypted content
        fontName: 'EncryptedFont',
        
        // CSS selectors to find article content (add more as needed)
        selectors: [
            'article',
            '.article-content',
            '.post-content',
            '[role="article"]',
            '.entry-content',
            '.story-body',
            '.article-body',
            '.content-body',
            '.post-body',
            '.article-text'
        ],
        
        // Minimum text length to encrypt (skip very short content)
        minTextLength: 10,
        
        // Maximum retries for API calls
        maxRetries: 3,
        
        // Retry delay in milliseconds
        retryDelay: 1000,
        
        // Enable client-side caching (don't re-encrypt same content)
        enableCache: true,
        
        // Cache size limit
        maxCacheSize: 1000
    };
    
    // ============================================================================
    // CLIENT-SIDE CACHING
    // ============================================================================
    const encryptionCache = new Map(); // Cache encrypted results
    
    /**
     * Generate cache key from text
     */
    function getCacheKey(text) {
        // Simple hash function for cache key
        let hash = 0;
        for (let i = 0; i < text.length; i++) {
            const char = text.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        return hash.toString();
    }
    
    /**
     * Get from cache or null if not found
     */
    function getCached(text) {
        if (!CONFIG.enableCache) return null;
        const key = getCacheKey(text);
        return encryptionCache.get(key) || null;
    }
    
    /**
     * Store in cache
     */
    function setCached(text, encrypted) {
        if (!CONFIG.enableCache) return;
        
        // Limit cache size
        if (encryptionCache.size >= CONFIG.maxCacheSize) {
            // Remove oldest entry (first key)
            const firstKey = encryptionCache.keys().next().value;
            encryptionCache.delete(firstKey);
        }
        
        const key = getCacheKey(text);
        encryptionCache.set(key, encrypted);
    }
    
    // ============================================================================
    // FONT LOADING
    // ============================================================================
    let fontLoaded = false;
    let fontLoadingPromise = null;
    
    /**
     * Load the custom encryption font
     * @param {string} fontUrl - URL to the font file
     * @returns {Promise<boolean>} - True if font loaded successfully
     */
    async function loadFont(fontUrl) {
        if (fontLoaded) {
            return true;
        }
        
        // If font is already loading, wait for that promise
        if (fontLoadingPromise) {
            return fontLoadingPromise;
        }
        
        fontLoadingPromise = (async () => {
            try {
                const font = new FontFace(CONFIG.fontName, `url(${fontUrl})`);
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
     * Encrypt text by calling the backend API (single)
     * @param {string} text - Text to encrypt
     * @param {number} retries - Number of retries remaining
     * @returns {Promise<Object>} - {encrypted, font_url}
     */
    async function encryptText(text, retries = CONFIG.maxRetries) {
        // Check cache first
        const cached = getCached(text);
        if (cached) {
            return cached;
        }
        
        try {
            const response = await fetch(CONFIG.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text })
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (!data.encrypted || !data.font_url) {
                throw new Error('Invalid API response');
            }
            
            // Cache the result
            setCached(text, data);
            
            return data;
            
        } catch (error) {
            if (retries > 0) {
                console.warn(`Encryption failed, retrying... (${retries} retries left)`);
                await new Promise(resolve => setTimeout(resolve, CONFIG.retryDelay));
                return encryptText(text, retries - 1);
            }
            throw error;
        }
    }
    
    /**
     * Encrypt multiple texts in batch (much more efficient)
     * @param {string[]} texts - Array of texts to encrypt
     * @param {number} retries - Number of retries remaining
     * @returns {Promise<Object>} - {encrypted: [...], font_url: "..."}
     */
    async function encryptTextBatch(texts, retries = CONFIG.maxRetries) {
        if (!texts || texts.length === 0) {
            return { encrypted: [], font_url: null };
        }
        
        // Check cache for each text, collect uncached ones
        const uncachedTexts = [];
        const uncachedIndices = [];
        const cachedResults = [];
        
        texts.forEach((text, index) => {
            const cached = getCached(text);
            if (cached) {
                cachedResults[index] = cached.encrypted;
            } else {
                uncachedTexts.push(text);
                uncachedIndices.push(index);
            }
        });
        
        // If all were cached, return cached results
        if (uncachedTexts.length === 0) {
            const firstCached = getCached(texts[0]);
            return {
                encrypted: cachedResults,
                font_url: firstCached.font_url
            };
        }
        
        try {
            const response = await fetch(CONFIG.batchEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ texts: uncachedTexts })
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (!data.encrypted || !Array.isArray(data.encrypted)) {
                throw new Error('Invalid API response');
            }
            
            // Merge cached and new results
            const allResults = [...cachedResults];
            uncachedIndices.forEach((originalIndex, batchIndex) => {
                allResults[originalIndex] = data.encrypted[batchIndex];
                // Cache the new result
                setCached(uncachedTexts[batchIndex], {
                    encrypted: data.encrypted[batchIndex],
                    font_url: data.font_url
                });
            });
            
            return {
                encrypted: allResults,
                font_url: data.font_url
            };
            
        } catch (error) {
            if (retries > 0) {
                console.warn(`Batch encryption failed, retrying... (${retries} retries left)`);
                await new Promise(resolve => setTimeout(resolve, CONFIG.retryDelay));
                return encryptTextBatch(texts, retries - 1);
            }
            throw error;
        }
    }
    
    // ============================================================================
    // ARTICLE ENCRYPTION
    // ============================================================================
    
    /**
     * Encrypt a single article element
     * @param {HTMLElement} element - Article element to encrypt
     */
    async function encryptArticle(element) {
        // Skip if already encrypted (has data attribute)
        if (element.dataset.encrypted === 'true') {
            return;
        }
        
        // Skip if element is too small or empty
        const originalText = element.textContent.trim();
        if (!originalText || originalText.length < CONFIG.minTextLength) {
            return;
        }
        
        try {
            // Mark as processing to avoid duplicate encryption attempts
            element.dataset.encrypting = 'true';
            
            // Call backend API to encrypt using exact algorithm
            const data = await encryptText(originalText);
            
            // Load the custom font
            const fontLoaded = await loadFont(data.font_url);
            if (!fontLoaded) {
                throw new Error('Font loading failed');
            }
            
            // Replace text with encrypted version
            element.textContent = data.encrypted;
            element.style.fontFamily = `${CONFIG.fontName}, sans-serif`;
            
            // Mark as encrypted
            element.dataset.encrypted = 'true';
            element.dataset.encrypting = 'false';
            
        } catch (error) {
            console.error('Encryption failed for article:', error);
            // On error, leave original text visible and mark as failed
            element.dataset.encrypting = 'false';
            element.dataset.encryptionFailed = 'true';
        }
    }
    
    /**
     * Find and encrypt all articles on the page
     * Uses batch API for better performance on high-traffic sites
     */
    async function encryptAllArticles() {
        const articles = []; // Array to maintain order
        
        // Find all article elements using various selectors
        CONFIG.selectors.forEach(selector => {
            try {
                const elements = document.querySelectorAll(selector);
                elements.forEach(el => {
                    // Only add if not already processing or encrypted
                    if (el.dataset.encrypting !== 'true' && 
                        el.dataset.encrypted !== 'true' &&
                        el.textContent.trim().length >= CONFIG.minTextLength) {
                        // Avoid duplicates
                        if (!articles.includes(el)) {
                            articles.push(el);
                        }
                    }
                });
            } catch (e) {
                // Invalid selector, skip it
                console.warn(`Invalid selector: ${selector}`);
            }
        });
        
        if (articles.length === 0) {
            return;
        }
        
        // Use batch API if enabled and multiple articles
        if (CONFIG.useBatch && articles.length > 1) {
            await encryptArticlesBatch(articles);
        } else {
            // Fall back to individual encryption
            articles.forEach(article => {
                encryptArticle(article);
            });
        }
    }
    
    /**
     * Encrypt multiple articles using batch API (much more efficient)
     * @param {HTMLElement[]} articles - Array of article elements
     */
    async function encryptArticlesBatch(articles) {
        // Extract texts and mark as processing
        const texts = [];
        const validArticles = [];
        
        articles.forEach(article => {
            const text = article.textContent.trim();
            if (text && text.length >= CONFIG.minTextLength) {
                texts.push(text);
                validArticles.push(article);
                article.dataset.encrypting = 'true';
            }
        });
        
        if (texts.length === 0) {
            return;
        }
        
        try {
            // Process in batches to avoid overwhelming the API
            const batchSize = CONFIG.batchSize;
            for (let i = 0; i < texts.length; i += batchSize) {
                const batchTexts = texts.slice(i, i + batchSize);
                const batchArticles = validArticles.slice(i, i + batchSize);
                
                // Encrypt batch
                const data = await encryptTextBatch(batchTexts);
                
                // Load font if not already loaded
                if (data.font_url) {
                    await loadFont(data.font_url);
                }
                
                // Apply encrypted text to each article
                batchArticles.forEach((article, index) => {
                    const encryptedText = data.encrypted[i + index];
                    if (encryptedText) {
                        article.textContent = encryptedText;
                        article.style.fontFamily = `${CONFIG.fontName}, sans-serif`;
                        article.dataset.encrypted = 'true';
                    }
                    article.dataset.encrypting = 'false';
                });
            }
        } catch (error) {
            console.error('Batch encryption failed:', error);
            // Mark all as failed
            validArticles.forEach(article => {
                article.dataset.encrypting = 'false';
                article.dataset.encryptionFailed = 'true';
            });
        }
    }
    
    // ============================================================================
    // INITIALIZATION
    // ============================================================================
    
    /**
     * Initialize the encryption system
     */
    function init() {
        // Encrypt articles immediately
        encryptAllArticles();
        
        // Watch for dynamically loaded content (SPA, infinite scroll, etc.)
        const observer = new MutationObserver((mutations) => {
            let shouldEncrypt = false;
            
            mutations.forEach(mutation => {
                if (mutation.addedNodes.length > 0) {
                    // Check if any added nodes match our selectors
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === 1) { // Element node
                            CONFIG.selectors.forEach(selector => {
                                if (node.matches && node.matches(selector)) {
                                    shouldEncrypt = true;
                                }
                                if (node.querySelector && node.querySelector(selector)) {
                                    shouldEncrypt = true;
                                }
                            });
                        }
                    });
                }
            });
            
            if (shouldEncrypt) {
                // Debounce: wait a bit for DOM to settle
                setTimeout(encryptAllArticles, 100);
            }
        });
        
        // Observe the entire document body for changes
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    
    // ============================================================================
    // AUTO-START
    // ============================================================================
    
    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // DOM already loaded, start immediately
        init();
    }
    
    // Also expose a manual function for advanced usage
    if (typeof window !== 'undefined') {
        window.encryptArticles = encryptAllArticles;
    }
    
})();

