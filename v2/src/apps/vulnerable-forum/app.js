const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const bodyParser = require('body-parser');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Database setup
const db = new sqlite3.Database('./forum.db');

// Middleware
app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());
app.use(express.static('public'));
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Initialize database tables
db.serialize(() => {
    // Posts table
    db.run(`CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        author TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);

    // Comments table
    db.run(`CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        author TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (post_id) REFERENCES posts (id)
    )`);

    // Insert sample data if tables are empty
    db.get("SELECT COUNT(*) as count FROM posts", (err, row) => {
        if (row.count === 0) {
            const samplePosts = [
                {
                    title: "Chào mừng đến với Forum!",
                    content: "Đây là bài viết đầu tiên trên forum. Hãy tham gia thảo luận!",
                    author: "Admin"
                },
                {
                    title: "Hướng dẫn sử dụng forum",
                    content: "Bạn có thể tạo bài viết mới, bình luận và tìm kiếm bài viết tại đây.",
                    author: "Admin"
                }
            ];

            samplePosts.forEach(post => {
                db.run("INSERT INTO posts (title, content, author) VALUES (?, ?, ?)", 
                    [post.title, post.content, post.author]);
            });
        }
    });
});

// Routes

// Home page - Show all posts
app.get('/', (req, res) => {
    const search = req.query.search || '';
    let query = "SELECT * FROM posts ORDER BY created_at DESC";
    let params = [];

    if (search) {
        query = "SELECT * FROM posts WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC";
        params = [`%${search}%`, `%${search}%`];
    }

    db.all(query, params, (err, posts) => {
        if (err) {
            console.error(err);
            return res.status(500).send('Database error');
        }
        res.render('index', { posts, search });
    });
});

// Show post detail with comments
app.get('/post/:id', (req, res) => {
    const postId = req.params.id;

    // Get post
    db.get("SELECT * FROM posts WHERE id = ?", [postId], (err, post) => {
        if (err) {
            console.error(err);
            return res.status(500).send('Database error');
        }
        if (!post) {
            return res.status(404).send('Post not found');
        }

        // Get comments for this post
        db.all("SELECT * FROM comments WHERE post_id = ? ORDER BY created_at ASC", [postId], (err, comments) => {
            if (err) {
                console.error(err);
                return res.status(500).send('Database error');
            }
            res.render('post-detail', { post, comments });
        });
    });
});

// Create new post (GET form)
app.get('/create', (req, res) => {
    res.render('create-post');
});

// Create new post (POST)
app.post('/create', (req, res) => {
    const { title, content, author } = req.body;
    
    if (!title || !content || !author) {
        return res.status(400).send('All fields are required');
    }

    db.run("INSERT INTO posts (title, content, author) VALUES (?, ?, ?)", 
        [title, content, author], function(err) {
        if (err) {
            console.error(err);
            return res.status(500).send('Database error');
        }
        res.redirect('/');
    });
});

// Add comment to post
app.post('/post/:id/comment', (req, res) => {
    const postId = req.params.id;
    const { author, content } = req.body;

    if (!author || !content) {
        return res.status(400).send('All fields are required');
    }

    db.run("INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)", 
        [postId, author, content], function(err) {
        if (err) {
            console.error(err);
            return res.status(500).send('Database error');
        }
        res.redirect(`/post/${postId}`);
    });
});

// Search posts
app.get('/search', (req, res) => {
    res.redirect('/?search=' + encodeURIComponent(req.query.q || ''));
});

// Start server
app.listen(PORT, () => {
    console.log(`Forum server is running on http://localhost:${PORT}`);
});

// Graceful shutdown
process.on('SIGINT', () => {
    db.close((err) => {
        if (err) {
            console.error(err.message);
        }
        console.log('Database connection closed.');
        process.exit(0);
    });
});
