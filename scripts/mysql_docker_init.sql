-- Chạy tự động khi container MySQL khởi tạo lần đầu.
-- Biến môi trường MYSQL_DATABASE/MYSQL_USER đã tạo sẵn database `vietjob`
-- và user `vietjob`; ở đây chỉ bổ sung database dùng cho test.

CREATE DATABASE IF NOT EXISTS vietjob_test
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON vietjob_test.* TO 'vietjob'@'%';
FLUSH PRIVILEGES;
