/**
 * Tests for Layer 1 - Application Layer
 * 
 * Mục đích: Test vulnerable forum app functionality & security
 * Bao gồm: SQLi testing, XSS testing, rate limiting, health checks
 */

const request = require('supertest');
const expect = require('chai').expect;
const express = require('express');

// Mock app cho testing
const createTestApp = () => {
    const app = express();
    const { 
        createRateLimiter, 
        securityHeaders, 
        requestLogger, 
        healthCheck 
    } = require('../middleware/security');
    
    app.use(securityHeaders);
    app.use(requestLogger);
    app.use(express.json());
    app.use(express.urlencoded({ extended: true }));
    
    // Test routes
    app.get('/health', healthCheck);
    app.get('/test', (req, res) => res.json({ message: 'test' }));
    app.post('/test', (req, res) => res.json({ received: req.body }));
    
    return app;
};

describe('Layer 1: Application Layer Tests', () => {
    let app;
    
    beforeEach(() => {
        app = createTestApp();
    });
    
    describe('Security Headers', () => {
        it('should add security headers to responses', async () => {
            const response = await request(app)
                .get('/test')
                .expect(200);
                
            expect(response.headers['x-frame-options']).to.equal('SAMEORIGIN');
            expect(response.headers['x-content-type-options']).to.equal('nosniff');
            expect(response.headers['referrer-policy']).to.equal('same-origin');
        });
    });
    
    describe('Health Check', () => {
        it('should return health status', async () => {
            const response = await request(app)
                .get('/health')
                .expect(200);
                
            expect(response.body).to.have.property('status', 'healthy');
            expect(response.body).to.have.property('timestamp');
            expect(response.body).to.have.property('uptime');
            expect(response.body).to.have.property('memory');
        });
    });
    
    describe('SQL Injection Detection', () => {
        const sqlInjectionPayloads = [
            "' OR '1'='1",
            "'; DROP TABLE posts; --",
            "' UNION SELECT * FROM users --",
            "%27%20OR%20%271%27%3D%271"
        ];
        
        sqlInjectionPayloads.forEach(payload => {
            it(`should detect SQLi attempt: ${payload}`, async () => {
                // Capture console.log để verify detection
                let loggedAttack = false;
                const originalLog = console.log;
                console.log = (...args) => {
                    if (args[0] && args[0].includes('[ATTACK_DETECTED]') && args[0].includes('SQLi')) {
                        loggedAttack = true;
                    }
                };
                
                await request(app)
                    .get(`/test?id=${encodeURIComponent(payload)}`)
                    .expect(200);
                
                console.log = originalLog;
                expect(loggedAttack).to.be.true;
            });
        });
    });
    
    describe('XSS Detection', () => {
        const xssPayloads = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            '<img src="x" onerror="alert(1)">',
            '<body onload="alert(1)">'
        ];
        
        xssPayloads.forEach(payload => {
            it(`should detect XSS attempt: ${payload}`, async () => {
                let loggedAttack = false;
                const originalLog = console.log;
                console.log = (...args) => {
                    if (args[0] && args[0].includes('[ATTACK_DETECTED]') && args[0].includes('XSS')) {
                        loggedAttack = true;
                    }
                };
                
                await request(app)
                    .post('/test')
                    .send({ content: payload })
                    .expect(200);
                
                console.log = originalLog;
                expect(loggedAttack).to.be.true;
            });
        });
    });
    
    describe('Rate Limiting', () => {
        it('should allow requests under limit', async () => {
            const rateLimitedApp = express();
            const { createRateLimiter } = require('../middleware/security');
            
            rateLimitedApp.use(createRateLimiter(60000, 5)); // 5 requests per minute
            rateLimitedApp.get('/test', (req, res) => res.json({ ok: true }));
            
            // Should allow first 5 requests
            for (let i = 0; i < 5; i++) {
                await request(rateLimitedApp)
                    .get('/test')
                    .expect(200);
            }
        });
        
        it('should block requests over limit', async () => {
            const rateLimitedApp = express();
            const { createRateLimiter } = require('../middleware/security');
            
            rateLimitedApp.use(createRateLimiter(60000, 2)); // 2 requests per minute
            rateLimitedApp.get('/test', (req, res) => res.json({ ok: true }));
            
            // First 2 should pass
            await request(rateLimitedApp).get('/test').expect(200);
            await request(rateLimitedApp).get('/test').expect(200);
            
            // 3rd should be blocked
            await request(rateLimitedApp).get('/test').expect(429);
        });
    });
    
    describe('Request Logging', () => {
        it('should log all requests with details', async () => {
            let loggedRequest = false;
            const originalLog = console.log;
            console.log = (...args) => {
                if (args[0] && args[0].includes('[REQUEST]')) {
                    loggedRequest = true;
                }
            };
            
            await request(app)
                .get('/test?param=value')
                .set('User-Agent', 'test-agent')
                .expect(200);
            
            console.log = originalLog;
            expect(loggedRequest).to.be.true;
        });
    });
});

module.exports = {
    createTestApp
};