# Forum Website

Website forum đơn giản được xây dựng với Express.js và SQLite3.

## Tính năng

- **Xem danh sách bài viết**: Hiển thị tất cả bài viết với tiêu đề, tác giả và thời gian
- **Chi tiết bài viết**: Xem nội dung đầy đủ của bài viết và bình luận
- **Thêm bình luận**: Bình luận trên các bài viết
- **Tìm kiếm bài viết**: Tìm kiếm theo tiêu đề và nội dung
- **Tạo bài viết mới**: Viết và đăng bài viết mới

## Cài đặt

1. **Cài đặt dependencies:**
   ```bash
   cd web-app
   npm install
   ```

2. **Chạy ứng dụng:**
   ```bash
   npm start
   ```
   
   Hoặc sử dụng nodemon để phát triển:
   ```bash
   npm run dev
   ```

3. **Mở trình duyệt:**
   ```
   http://localhost:3000
   ```

## Cấu trúc dự án

```
web-app/
├── app.js              # File chính của ứng dụng
├── package.json        # Dependencies và scripts
├── forum.db           # Database SQLite3 (tự động tạo)
├── public/
│   └── css/
│       └── style.css   # CSS styling
└── views/
    ├── layout.ejs      # Template layout chung
    ├── index.ejs       # Trang danh sách bài viết
    ├── post-detail.ejs # Trang chi tiết bài viết
    └── create-post.ejs # Trang tạo bài viết mới
```

## Công nghệ sử dụng

- **Backend**: Node.js, Express.js
- **Database**: SQLite3
- **Template Engine**: EJS
- **Styling**: CSS3 với Flexbox/Grid
- **Icons**: Font Awesome

## Database Schema

### Bảng Posts
- `id`: Primary key
- `title`: Tiêu đề bài viết
- `content`: Nội dung bài viết
- `author`: Tác giả
- `created_at`: Thời gian tạo

### Bảng Comments
- `id`: Primary key
- `post_id`: Foreign key tới bảng posts
- `author`: Tác giả bình luận
- `content`: Nội dung bình luận
- `created_at`: Thời gian tạo

## API Endpoints

- `GET /`: Trang chủ - danh sách bài viết
- `GET /post/:id`: Chi tiết bài viết
- `GET /create`: Form tạo bài viết mới
- `POST /create`: Tạo bài viết mới
- `POST /post/:id/comment`: Thêm bình luận
- `GET /?search=query`: Tìm kiếm bài viết

## Tính năng

### Tìm kiếm
- Tìm kiếm theo tiêu đề và nội dung bài viết
- Sử dụng LIKE query trong SQLite
- Giao diện tìm kiếm responsive

### Responsive Design
- Tối ưu cho desktop, tablet và mobile
- Sử dụng CSS Grid và Flexbox
- Navigation thân thiện với mobile

### UX Features
- Smooth animations và transitions
- Form validation
- Keyboard shortcuts (nhấn '/' để focus vào search)
- Loading states và error handling
