/**
 * Security Middleware cho Vulnerable Forum
 * 
 * Mục đích: Thêm basic security mà không phá vỡ tính vulnerable
 * Tại sao: Cần balance giữa realistic app vs intentional vulnerabilities
 * Cách khác: Có thể dùng helmet.js nhưng sẽ block nhiều attacks
 */

const rateLimit = require('express-rate-limit');

// Basic rate limiting - loose để cho phép testing attacks
const createRateLimiter = (windowMs = 15 * 60 * 1000, max = 1000) => {
    return rateLimit({
        windowMs,
        max,
        message: 'Too many requests from this IP, please try again later.',
        standardHeaders: true,
        legacyHeaders: false,
        // Custom handler để log attack attempts
        handler: (req, res, next) => {
            console.log(`[RATE_LIMIT] ${req.ip} exceeded ${max} requests in ${windowMs/1000}s`);
            res.status(429).json({
                error: 'Rate limit exceeded',
                retryAfter: Math.round(windowMs / 1000)
            });
        }
    });
};

// Security headers middleware
const securityHeaders = (req, res, next) => {
    // Basic security headers (not too strict)
    res.setHeader('X-Frame-Options', 'SAMEORIGIN');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'same-origin');
    
    // Log all requests for monitoring
    console.log(`[REQUEST] ${req.method} ${req.url} from ${req.ip}`);
    
    next();
};

// Request logging với detailed info cho detection
const requestLogger = (req, res, next) => {
    const requestInfo = {
        timestamp: new Date().toISOString(),
        method: req.method,
        url: req.url,
        ip: req.ip,
        userAgent: req.get('User-Agent'),
        headers: req.headers,
        query: req.query,
        body: req.body,
        contentLength: req.get('Content-Length') || 0
    };
    
    // Detect potential attacks in query/body
    const suspiciousPatterns = [
        // SQLi patterns
        /(\%27)|(\')|(\-\-)|(\%23)|(#)/i,
        /(\%3D)|(=)[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))/i,
        /((\%27)|(\'))union/i,
        /exec(\s|\+)+(s|x)p\w+/i,
        
        // XSS patterns
        /<script[^>]*>.*?<\/script>/i,
        /javascript:/i,
        /onerror\s*=/i,
        /onload\s*=/i
    ];
    
    const queryString = JSON.stringify(req.query);
    const bodyString = JSON.stringify(req.body);
    
    let attackType = null;
    suspiciousPatterns.forEach((pattern, index) => {
        if (pattern.test(queryString) || pattern.test(bodyString)) {
            attackType = index < 4 ? 'SQLi' : 'XSS';
        }
    });
    
    if (attackType) {
        console.log(`[ATTACK_DETECTED] ${attackType} from ${req.ip}: ${req.url}`);
        requestInfo.attackType = attackType;
        requestInfo.suspicious = true;
    }
    
    // Store request info cho analysis
    req.requestInfo = requestInfo;
    
    next();
};

// Health check endpoint
const healthCheck = (req, res) => {
    const health = {
        status: 'healthy',
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
        memory: process.memoryUsage(),
        version: process.env.npm_package_version || '1.0.0'
    };
    
    res.status(200).json(health);
};

module.exports = {
    createRateLimiter,
    securityHeaders,
    requestLogger,
    healthCheck
};