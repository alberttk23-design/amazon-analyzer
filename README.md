# 📦 Amazon Analyzer — DTC & E-Commerce Product Intelligence Suite

Một hệ thống phân tích thị trường và trí tuệ sản phẩm chuyên sâu dành riêng cho nhà bán hàng **Amazon (US Marketplace)**, thương hiệu DTC và Private Label sellers.

Được kế thừa 100% bộ khung kiến trúc chuẩn và trải nghiệm người dùng cao cấp từ **TikTok Analyzer**, chuyển đổi tối ưu hóa cho các chỉ số đặc thù của sàn Amazon US.

---

## 🌟 Tính Năng Cốt Lõi & Kiến Trúc v2.0 (Acquisition Before Analysis)

### 1. Triết Lý "Acquisition Before Analysis" & Candidate Universe
- **Xây dựng Candidate Universe không bỏ sót**: Thu thập tối đa ứng viên trước khi xếp hạng hoặc lọc sâu. Không bao giờ gạt bỏ sản phẩm ngoài top (tránh bỏ lỡ emerging winners).
- **Hệ thống phân tầng ứng viên (Candidate Tiers)**:
  - `COLD`: Lưu trữ toàn bộ ứng viên phát hiện được, không bao giờ bị xóa.
  - `WARM`: Ứng viên có tín hiệu tăng trưởng (Review velocity, Ads active, Outlier giá).
  - `HOT`: Các đối thủ cốt lõi được ưu tiên cào sâu thông số & toàn bộ reviews.
- **Saturation Curve & Coverage Ledger**: Bảng theo dõi hiệu suất biên (Marginal Yield) và tỷ lệ trùng lặp theo từng trang / từng làn tìm kiếm.
- **Tách bạch Search Observations**: Lưu ngữ cảnh từng lần xuất hiện (Sponsored vs Organic, vị trí rank, số trang, coupon, huy hiệu) độc lập với entity sản phẩm.

### 2. Quản Lý Ngách Sản Phẩm (Multi-Niche Folders) & Checkpoint Queue
- **Cách ly dữ liệu từng ngách**: Phân loại và nghiên cứu độc lập từng dòng sản phẩm (*Luggage*, *Portable Blender*, *Olive Oil Sprayer*, *Migraine Relief Cap*...).
- **Checkpoint & Resume Queue**: Hàng đợi các truy vấn tìm kiếm tự động checkpoint vào SQLite; cho phép tạm dừng và bấm Resume tiếp tục bất cứ lúc nào mà không cào trùng lặp.
- **Diagnostics Dumps (amkarpe pattern)**: Tự động lưu dump mã nguồn HTML (`data/debug/html/`) và ảnh chụp màn hình PNG (`data/debug/screenshots/`) khi gặp Captcha hoặc lỗi phân tích để dễ dàng kiểm tra trực quan trên Dashboard.
- **SQLite WAL Mode (`busy_timeout=30000`)**: Hỗ trợ đồng thời cào dữ liệu chạy ngầm trong BackgroundTasks, tra cứu tức thì và không bị khóa database.

### 3. Playwright Engine & Chiến Lược Fallback (Strategy Ladder)
- **Tự động áp dụng Zip Code 10001 (New York, US)**: Đảm bảo 100% dữ liệu về giá bán, tồn kho và phí vận chuyển hiển thị chuẩn theo thị trường nội địa Mỹ.
- **Strategy Ladder (Tiered Fetcher)**:
  - *Level 1*: Fast Direct HTTP Requests tốc độ cao.
  - *Level 2*: Tự động chuyển đổi sang Playwright Headless Browser có persistent session khi Amazon yêu cầu xác thực hoặc chống bot.
  - *Level 3*: Hỗ trợ mở GUI Browser thật để người dùng giải Captcha hoặc đổi tài khoản thủ công khi cần.

### 4. Bóc Tách Biến Thể Chuyên Sâu (Spigen Twister Architecture)
- **Parent/Child ASIN Mapping**: Phân tích trực tiếp từ dữ liệu nội tại `twister-plus` (`dimensionValuesDisplayData`, `asinToDimensionIndexMap`), xác định chính xác Parent ASIN và tất cả Child ASINs.
- **Bảo tồn Biến thể độc lập**: Mọi biến thể con (màu sắc, kích cỡ, dung tích) đều được lưu trữ như một thực thể độc lập trong Database, có đầy đủ SKU và thuộc tính riêng mà không bị làm phẳng (flattening).

### 5. Bộ Cào Dữ Liệu Sản Phẩm Amazon (Product Velocity Scraper)
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
