-- ============================================================
--  VietJob Korea AI — MySQL bootstrap
--
--  TRƯỚC KHI CHẠY:
--    1. Copy file này thành scripts/mysql_setup.local.sql (đã được gitignore)
--    2. Thay 'CHANGE_ME_STRONG_PASSWORD' bằng mật khẩu bạn tự chọn
--    3. Dùng đúng mật khẩu đó trong .env
--
--  CÁCH CHẠY (PowerShell, sẽ hỏi mật khẩu root của bạn):
--
--    & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p `
--        -e "source scripts/mysql_setup.local.sql"
--
--  Dùng `-e "source ..."` chứ KHÔNG dùng `< file`: PowerShell không hỗ trợ
--  toán tử `<` và sẽ báo lỗi cú pháp. Trên Linux/macOS thì `< file` chạy bình
--  thường:  mysql -u root -p < scripts/mysql_setup.local.sql
-- ============================================================

-- utf8mb4 là bắt buộc: dữ liệu gồm tiếng Việt có dấu, tiếng Hàn và emoji.
CREATE DATABASE IF NOT EXISTS vietjob
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS vietjob_test
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- User riêng cho ứng dụng. Không dùng root để chạy app.
CREATE USER IF NOT EXISTS 'vietjob'@'localhost'
  IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';
CREATE USER IF NOT EXISTS 'vietjob'@'127.0.0.1'
  IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';

GRANT ALL PRIVILEGES ON vietjob.*      TO 'vietjob'@'localhost';
GRANT ALL PRIVILEGES ON vietjob.*      TO 'vietjob'@'127.0.0.1';
GRANT ALL PRIVILEGES ON vietjob_test.* TO 'vietjob'@'localhost';
GRANT ALL PRIVILEGES ON vietjob_test.* TO 'vietjob'@'127.0.0.1';

FLUSH PRIVILEGES;

-- ------------------------------------------------------------
--  Kiểm tra cấu hình phục vụ full-text search tiếng Hàn.
--
--  MySQL dùng parser `ngram` cho ngôn ngữ không tách từ bằng
--  khoảng trắng (Hàn, Nhật, Trung). ngram_token_size=2 là mặc
--  định và phù hợp cho tiếng Hàn.
--
--  ngram_token_size là biến CHỈ ĐỌC lúc chạy — muốn đổi phải sửa
--  my.ini rồi restart service. Giá trị mặc định 2 đã đủ dùng,
--  KHÔNG cần đổi.
-- ------------------------------------------------------------
SELECT @@ngram_token_size            AS ngram_token_size,
       @@innodb_ft_min_token_size    AS innodb_ft_min_token_size,
       @@character_set_server        AS charset_server,
       VERSION()                     AS mysql_version;

SELECT SCHEMA_NAME, DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME
  FROM information_schema.SCHEMATA
 WHERE SCHEMA_NAME IN ('vietjob', 'vietjob_test');
