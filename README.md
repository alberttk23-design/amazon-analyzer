# 📦 Amazon Analyzer — DTC & E-Commerce Product Intelligence Suite

Một hệ thống phân tích thị trường và trí tuệ sản phẩm chuyên sâu dành riêng cho nhà bán hàng **Amazon (US Marketplace)**, thương hiệu DTC và Private Label sellers.

Được kế thừa 100% bộ khung kiến trúc chuẩn và trải nghiệm người dùng cao cấp từ **TikTok Analyzer**, chuyển đổi tối ưu hóa cho các chỉ số đặc thù của sàn Amazon US.

---

## 🌟 Tính Năng Cốt Lõi & Kiến Trúc Kế Thừa

### 1. Quản Lý Ngách Sản Phẩm (Multi-Niche Folders)
- **Cách ly dữ liệu từng ngách**: Phân loại và nghiên cứu độc lập từng dòng sản phẩm (*Portable Blender*, *Olive Oil Sprayer*, *Faux Olive Tree*...).
- **Gộp Niche an toàn**: Gộp dữ liệu sản phẩm trùng lặp mà không bị mất lịch sử đánh giá hoặc trùng lặp ASIN.
- **SQLite WAL Mode (`busy_timeout=30000`)**: Hỗ trợ đồng thời cào dữ liệu chạy ngầm trong BackgroundTasks, tra cứu tức thì và không bị khóa database.

### 2. Playwright Engine Chuyên Biệt Cho Amazon US
- **Tự động áp dụng Zip Code 10001 (New York, US)**: Đảm bảo 100% dữ liệu về giá bán, tồn kho và phí vận chuyển hiển thị chuẩn theo thị trường nội địa Mỹ.
- **Persistent Browser Profile**: Lưu giữ cookies, token và trạng thái trình duyệt tại `data/browser_profile`, giảm thiểu tỷ lệ dính Captcha.
- **Interactive GUI Browser**: Tính năng mở trực tiếp trình duyệt Chromium trên màn hình macOS để đăng nhập tài khoản Amazon seller hoặc giải captcha khi cần.

### 3. Bộ Cào Dữ Liệu Sản Phẩm Amazon (Product Velocity Scraper)
- **Bóc tách chi tiết**: ASIN, Tiêu đề, Thương hiệu, BuyBox seller, Giá bán, Giá niêm yết (List price), Điểm sao (★), Tổng lượt đánh giá, Số lượng bán tháng qua (*"2K+ bought in past month"*), BSR Rank.
- **Nhận diện Badges**: Tự động đánh dấu sản phẩm đạt *#1 Best Seller*, *Amazon's Choice*, *Overall Pick* hoặc chạy *Sponsored Ads*.
- **Tính toán Product Viability Score**: Chấm điểm tiềm năng kinh doanh (0 - 100 điểm) dựa trên tốc độ bán, độ hài lòng và độ cạnh tranh.

### 4. Bóc Tách Voice of Customer (VoC 6 Trụ Cột E-Commerce)
- **Tập trung bóc tách có chủ đích**:
  - **Review tiêu cực (1-3★)**: Tìm ra lỗi sản phẩm chí mạng, độ bền kém, rò rỉ, linh kiện ọp ẹp và lý do khách hàng trả hàng của đối thủ.
  - **Review tích cực (5★)**: Khám phá động lực chốt đơn, tính năng ăn tiền và lý do khách chọn sản phẩm thay vì các nhãn hàng khác.
- **Khung 6 Trụ cột Phân tích**:
  1. *Lỗi Kỹ Thuật & Độ Bền Kém (Product Defects & Durability)*
  2. *Sai Lệch Listing & Kỳ Vọng Thất Vọng (Misleading Listing & Expectation Gap)*
  3. *Đóng Gói, Vận Chuyển & Lắp Đặt Hư Hỏng (Packaging, Shipping & Assembly)*
  4. *Giá Trị Thực vs Chi Phí & Lý Do Trả Hàng (Price-to-Value & Returns)*
  5. *Yếu Tố Ăn Tiền & Động Lực Chốt Đơn 5★ (Hero Features & Buying Triggers)*
  6. *Chỉ Thị Nâng Cấp Sản Phẩm Cho Seller (Sourcing & Listing Optimization)*

### 5. Sponsored Ads & BSR Top 100 Leaderboard
- **Mật độ quảng cáo đấu thầu (Sponsored Ads)**: Đo lường tỷ lệ cạnh tranh PPC trên trang tìm kiếm.
- **Bảng xếp hạng Best Sellers**: Quét danh sách top 100 sản phẩm dẫn đầu danh mục.

### 6. Dual AI Engine: Gemini & Local Synthesis
- **Chỉ thị xưởng sản xuất (Factory Directives)**: Checklist cụ thể về vật liệu, khuôn đúc, bao bì chống sốc để đàm phán trực tiếp với xưởng OEM/ODM.
- **Amazon Listing Optimization Blueprint**:
  - Tiêu đề chuẩn SEO Amazon chứa từ khóa chuyển đổi cao.
  - 5 Bullet Points nhấn mạnh giải quyết triệt để các pain points từ review 1-3 sao của đối thủ.
  - Backend Search Terms ngầm (< 249 bytes, không trùng từ).
  - Kế hoạch hình ảnh Infographics & bố cục A+ Content (EBC).

### 7. Xuất Dữ Liệu Excel Chuẩn UTF-8 BOM
- Xuất file CSV định dạng UTF-8 BOM hiển thị chuẩn tiếng Việt và ký tự đặc biệt trong Microsoft Excel (`/api/export/csv`).
- Xuất toàn bộ cấu trúc dữ liệu JSON để tích hợp với các LLM bên ngoài (`/api/export/json`).

---

## 🛠️ Hướng Dẫn Cài Đặt & Khởi Động

### 1. Yêu cầu hệ thống
- **Hệ điều hành**: macOS (Apple Silicon M-series hoặc Intel)
- **Python**: 3.10+
- **Node.js**: 18+

### 2. Khởi chạy một chạm (Quickstart)
```bash
cd /Users/dudumac5/AI-Projects/amazon-analyzer

# Cấp quyền thực thi và khởi động toàn bộ hệ thống
chmod +x start_app.sh
./start_app.sh
```

- **Giao diện Web Dashboard**: `http://localhost:5174`
- **Tài liệu API Backend**: `http://127.0.0.1:8001/docs`

> **Lưu ý về cổng mạng (Ports)**:
> Amazon Analyzer sử dụng Backend port `8001` và Frontend port `5174` nên bạn có thể chạy đồng thời cả **TikTok Analyzer** (8000 / 5173) và **Amazon Analyzer** cùng lúc trên máy mà không sợ xung đột port.
