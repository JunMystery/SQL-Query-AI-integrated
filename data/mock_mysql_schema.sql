-- Mock MySQL database for SQLBot Desktop text-to-SQL testing.
-- Usage:
--   mysql -u root -p < data/mock_mysql_schema.sql
--
-- The schema models a small Vietnamese retail/CRM business with enough
-- relationships and sample data to test joins, filters, aggregations, dates,
-- ranking, grouping, and reporting queries.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP DATABASE IF EXISTS sqlbot_mock;
CREATE DATABASE sqlbot_mock
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE sqlbot_mock;

DROP VIEW IF EXISTS v_order_summary;
DROP TABLE IF EXISTS support_tickets;
DROP TABLE IF EXISTS shipments;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS inventory_movements;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS departments;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE departments (
  department_id INT AUTO_INCREMENT PRIMARY KEY,
  department_code VARCHAR(20) NOT NULL UNIQUE,
  department_name VARCHAR(100) NOT NULL,
  location VARCHAR(100) NOT NULL,
  budget DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE employees (
  employee_id INT AUTO_INCREMENT PRIMARY KEY,
  department_id INT NOT NULL,
  manager_id INT NULL,
  employee_code VARCHAR(20) NOT NULL UNIQUE,
  full_name VARCHAR(120) NOT NULL,
  job_title VARCHAR(100) NOT NULL,
  hire_date DATE NOT NULL,
  salary DECIMAL(14,2) NOT NULL,
  status ENUM('active', 'inactive', 'probation') NOT NULL DEFAULT 'active',
  CONSTRAINT fk_employees_department
    FOREIGN KEY (department_id) REFERENCES departments(department_id),
  CONSTRAINT fk_employees_manager
    FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
) ENGINE=InnoDB;

CREATE TABLE customers (
  customer_id INT AUTO_INCREMENT PRIMARY KEY,
  customer_code VARCHAR(20) NOT NULL UNIQUE,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(160) NOT NULL UNIQUE,
  phone VARCHAR(30) NOT NULL,
  city VARCHAR(80) NOT NULL,
  segment ENUM('retail', 'business', 'vip') NOT NULL DEFAULT 'retail',
  registered_at DATETIME NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  INDEX idx_customers_city (city),
  INDEX idx_customers_segment (segment)
) ENGINE=InnoDB;

CREATE TABLE categories (
  category_id INT AUTO_INCREMENT PRIMARY KEY,
  category_name VARCHAR(100) NOT NULL UNIQUE,
  parent_category_id INT NULL,
  CONSTRAINT fk_categories_parent
    FOREIGN KEY (parent_category_id) REFERENCES categories(category_id)
) ENGINE=InnoDB;

CREATE TABLE suppliers (
  supplier_id INT AUTO_INCREMENT PRIMARY KEY,
  supplier_code VARCHAR(20) NOT NULL UNIQUE,
  supplier_name VARCHAR(140) NOT NULL,
  city VARCHAR(80) NOT NULL,
  contact_name VARCHAR(120) NOT NULL,
  phone VARCHAR(30) NOT NULL,
  rating DECIMAL(3,2) NOT NULL DEFAULT 4.00,
  is_active TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE products (
  product_id INT AUTO_INCREMENT PRIMARY KEY,
  category_id INT NOT NULL,
  supplier_id INT NOT NULL,
  sku VARCHAR(40) NOT NULL UNIQUE,
  product_name VARCHAR(160) NOT NULL,
  unit_price DECIMAL(14,2) NOT NULL,
  cost_price DECIMAL(14,2) NOT NULL,
  stock_quantity INT NOT NULL DEFAULT 0,
  reorder_level INT NOT NULL DEFAULT 10,
  status ENUM('active', 'discontinued') NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_products_category
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
  CONSTRAINT fk_products_supplier
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
  INDEX idx_products_category (category_id),
  INDEX idx_products_supplier (supplier_id),
  INDEX idx_products_stock (stock_quantity)
) ENGINE=InnoDB;

CREATE TABLE orders (
  order_id INT AUTO_INCREMENT PRIMARY KEY,
  order_code VARCHAR(30) NOT NULL UNIQUE,
  customer_id INT NOT NULL,
  sales_employee_id INT NOT NULL,
  order_date DATETIME NOT NULL,
  status ENUM('draft', 'confirmed', 'shipped', 'completed', 'cancelled') NOT NULL,
  channel ENUM('store', 'website', 'marketplace', 'phone') NOT NULL,
  shipping_city VARCHAR(80) NOT NULL,
  shipping_fee DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  note VARCHAR(255) NULL,
  CONSTRAINT fk_orders_customer
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
  CONSTRAINT fk_orders_employee
    FOREIGN KEY (sales_employee_id) REFERENCES employees(employee_id),
  INDEX idx_orders_customer (customer_id),
  INDEX idx_orders_employee (sales_employee_id),
  INDEX idx_orders_date (order_date),
  INDEX idx_orders_status (status)
) ENGINE=InnoDB;

CREATE TABLE order_items (
  order_item_id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL,
  unit_price DECIMAL(14,2) NOT NULL,
  discount_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  tax_rate DECIMAL(5,2) NOT NULL DEFAULT 8.00,
  CONSTRAINT fk_order_items_order
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
  CONSTRAINT fk_order_items_product
    FOREIGN KEY (product_id) REFERENCES products(product_id),
  INDEX idx_order_items_order (order_id),
  INDEX idx_order_items_product (product_id)
) ENGINE=InnoDB;

CREATE TABLE payments (
  payment_id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  payment_date DATETIME NOT NULL,
  method ENUM('cash', 'bank_transfer', 'credit_card', 'e_wallet') NOT NULL,
  amount DECIMAL(14,2) NOT NULL,
  status ENUM('pending', 'paid', 'failed', 'refunded') NOT NULL,
  transaction_ref VARCHAR(80) NULL,
  CONSTRAINT fk_payments_order
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
  INDEX idx_payments_order (order_id),
  INDEX idx_payments_status (status),
  INDEX idx_payments_date (payment_date)
) ENGINE=InnoDB;

CREATE TABLE shipments (
  shipment_id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL UNIQUE,
  carrier VARCHAR(80) NOT NULL,
  tracking_code VARCHAR(80) NOT NULL UNIQUE,
  shipped_at DATETIME NULL,
  delivered_at DATETIME NULL,
  shipping_status ENUM('preparing', 'in_transit', 'delivered', 'returned') NOT NULL,
  CONSTRAINT fk_shipments_order
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
  INDEX idx_shipments_status (shipping_status)
) ENGINE=InnoDB;

CREATE TABLE inventory_movements (
  movement_id INT AUTO_INCREMENT PRIMARY KEY,
  product_id INT NOT NULL,
  movement_date DATETIME NOT NULL,
  movement_type ENUM('purchase', 'sale', 'return', 'adjustment') NOT NULL,
  quantity_change INT NOT NULL,
  reference_code VARCHAR(50) NULL,
  note VARCHAR(255) NULL,
  CONSTRAINT fk_inventory_product
    FOREIGN KEY (product_id) REFERENCES products(product_id),
  INDEX idx_inventory_product (product_id),
  INDEX idx_inventory_date (movement_date),
  INDEX idx_inventory_type (movement_type)
) ENGINE=InnoDB;

CREATE TABLE support_tickets (
  ticket_id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  order_id INT NULL,
  assigned_employee_id INT NULL,
  ticket_code VARCHAR(30) NOT NULL UNIQUE,
  subject VARCHAR(180) NOT NULL,
  priority ENUM('low', 'medium', 'high', 'urgent') NOT NULL DEFAULT 'medium',
  status ENUM('open', 'in_progress', 'resolved', 'closed') NOT NULL DEFAULT 'open',
  created_at DATETIME NOT NULL,
  resolved_at DATETIME NULL,
  CONSTRAINT fk_tickets_customer
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
  CONSTRAINT fk_tickets_order
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
  CONSTRAINT fk_tickets_employee
    FOREIGN KEY (assigned_employee_id) REFERENCES employees(employee_id),
  INDEX idx_tickets_customer (customer_id),
  INDEX idx_tickets_status (status),
  INDEX idx_tickets_priority (priority)
) ENGINE=InnoDB;

INSERT INTO departments (department_id, department_code, department_name, location, budget) VALUES
  (1, 'SALES', 'Kinh doanh', 'Ha Noi', 1200000000.00),
  (2, 'OPS', 'Van hanh', 'Ho Chi Minh', 900000000.00),
  (3, 'CS', 'Cham soc khach hang', 'Da Nang', 550000000.00),
  (4, 'FIN', 'Tai chinh', 'Ha Noi', 700000000.00);

INSERT INTO employees (employee_id, department_id, manager_id, employee_code, full_name, job_title, hire_date, salary, status) VALUES
  (1, 1, NULL, 'E001', 'Nguyen Minh Anh', 'Sales Manager', '2021-01-10', 42000000.00, 'active'),
  (2, 1, 1, 'E002', 'Tran Quang Huy', 'Sales Executive', '2022-03-15', 22000000.00, 'active'),
  (3, 1, 1, 'E003', 'Le Thu Ha', 'Sales Executive', '2023-06-01', 21000000.00, 'active'),
  (4, 2, NULL, 'E004', 'Pham Duc Long', 'Operations Manager', '2020-09-20', 39000000.00, 'active'),
  (5, 3, NULL, 'E005', 'Do Mai Linh', 'Customer Support Lead', '2021-11-05', 30000000.00, 'active'),
  (6, 3, 5, 'E006', 'Hoang Bao Chau', 'Support Specialist', '2024-02-12', 16000000.00, 'probation'),
  (7, 4, NULL, 'E007', 'Vu Thanh Tung', 'Accountant', '2022-08-22', 25000000.00, 'active');

INSERT INTO customers (customer_id, customer_code, full_name, email, phone, city, segment, registered_at, is_active) VALUES
  (1, 'C001', 'Cong ty An Phat', 'contact@anphat.example', '0901000001', 'Ha Noi', 'business', '2023-01-05 09:15:00', 1),
  (2, 'C002', 'Nguyen Thi Lan', 'lan.nguyen@example.com', '0901000002', 'Ho Chi Minh', 'vip', '2023-02-18 14:30:00', 1),
  (3, 'C003', 'Tran Van Nam', 'nam.tran@example.com', '0901000003', 'Da Nang', 'retail', '2023-04-20 08:05:00', 1),
  (4, 'C004', 'Cong ty Sao Viet', 'hello@saoviet.example', '0901000004', 'Hai Phong', 'business', '2023-07-11 10:45:00', 1),
  (5, 'C005', 'Le Hoai Thu', 'thu.le@example.com', '0901000005', 'Can Tho', 'retail', '2023-09-03 16:20:00', 1),
  (6, 'C006', 'Pham Gia Bao', 'bao.pham@example.com', '0901000006', 'Ha Noi', 'vip', '2024-01-14 11:00:00', 1),
  (7, 'C007', 'Doanh nghiep Mekong Xanh', 'sales@mekongxanh.example', '0901000007', 'Can Tho', 'business', '2024-03-09 13:40:00', 1),
  (8, 'C008', 'Hoang Anh Duong', 'duong.hoang@example.com', '0901000008', 'Nha Trang', 'retail', '2024-05-22 17:10:00', 0);

INSERT INTO categories (category_id, category_name, parent_category_id) VALUES
  (1, 'Dien tu', NULL),
  (2, 'Gia dung', NULL),
  (3, 'Van phong', NULL),
  (4, 'Laptop', 1),
  (5, 'Phu kien', 1),
  (6, 'May in', 3),
  (7, 'Thiet bi bep', 2);

INSERT INTO suppliers (supplier_id, supplier_code, supplier_name, city, contact_name, phone, rating, is_active) VALUES
  (1, 'S001', 'TechSource Viet Nam', 'Ho Chi Minh', 'Bui Khac Nam', '0287000001', 4.70, 1),
  (2, 'S002', 'Ha Noi Office Supply', 'Ha Noi', 'Ngo Thanh Mai', '0247000002', 4.35, 1),
  (3, 'S003', 'Da Nang HomeTech', 'Da Nang', 'Truong Minh Duc', '0236700003', 4.10, 1),
  (4, 'S004', 'Sai Gon Premium Goods', 'Ho Chi Minh', 'Dang Nhat Linh', '0287000004', 4.85, 1);

INSERT INTO products (product_id, category_id, supplier_id, sku, product_name, unit_price, cost_price, stock_quantity, reorder_level, status) VALUES
  (1, 4, 1, 'LAP-ACER-14', 'Laptop Acer 14 inch', 14500000.00, 11800000.00, 18, 5, 'active'),
  (2, 4, 4, 'LAP-DELL-15', 'Laptop Dell 15 inch', 18900000.00, 15400000.00, 9, 4, 'active'),
  (3, 5, 1, 'MOU-WL-01', 'Chuot khong day', 320000.00, 180000.00, 95, 20, 'active'),
  (4, 5, 1, 'KEY-MECH-01', 'Ban phim co', 1250000.00, 820000.00, 40, 10, 'active'),
  (5, 6, 2, 'PRN-LASER-01', 'May in laser don nang', 3650000.00, 2850000.00, 14, 3, 'active'),
  (6, 7, 3, 'BLD-POWER-01', 'May xay sinh to', 890000.00, 560000.00, 32, 8, 'active'),
  (7, 7, 3, 'RCK-ELEC-01', 'Noi com dien 1.8L', 1150000.00, 760000.00, 25, 8, 'active'),
  (8, 3, 2, 'CHA-ERG-01', 'Ghe van phong ergonomic', 2450000.00, 1700000.00, 11, 5, 'active'),
  (9, 5, 4, 'HUB-USB-01', 'Hub USB-C 7 cong', 790000.00, 480000.00, 7, 10, 'active'),
  (10, 1, 1, 'TAB-10-01', 'May tinh bang 10 inch', 6990000.00, 5400000.00, 0, 5, 'discontinued');

INSERT INTO orders (order_id, order_code, customer_id, sales_employee_id, order_date, status, channel, shipping_city, shipping_fee, note) VALUES
  (1, 'ORD-2024-0001', 1, 2, '2024-01-12 10:20:00', 'completed', 'website', 'Ha Noi', 45000.00, 'Khach doanh nghiep'),
  (2, 'ORD-2024-0002', 2, 3, '2024-01-20 15:05:00', 'completed', 'store', 'Ho Chi Minh', 0.00, NULL),
  (3, 'ORD-2024-0003', 3, 2, '2024-02-03 09:40:00', 'shipped', 'marketplace', 'Da Nang', 35000.00, NULL),
  (4, 'ORD-2024-0004', 4, 1, '2024-02-14 11:25:00', 'completed', 'phone', 'Hai Phong', 65000.00, 'Can hoa don VAT'),
  (5, 'ORD-2024-0005', 5, 3, '2024-03-08 18:10:00', 'cancelled', 'website', 'Can Tho', 50000.00, 'Khach huy truoc khi giao'),
  (6, 'ORD-2024-0006', 6, 2, '2024-03-19 13:50:00', 'completed', 'website', 'Ha Noi', 45000.00, NULL),
  (7, 'ORD-2024-0007', 7, 1, '2024-04-05 08:35:00', 'confirmed', 'phone', 'Can Tho', 70000.00, 'Don so luong lon'),
  (8, 'ORD-2024-0008', 2, 3, '2024-04-21 20:15:00', 'completed', 'marketplace', 'Ho Chi Minh', 25000.00, NULL),
  (9, 'ORD-2024-0009', 1, 2, '2024-05-10 14:45:00', 'shipped', 'website', 'Ha Noi', 45000.00, NULL),
  (10, 'ORD-2024-0010', 8, 3, '2024-05-18 16:00:00', 'draft', 'store', 'Nha Trang', 55000.00, 'Dang cho xac nhan');

INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount_amount, tax_rate) VALUES
  (1, 1, 2, 14500000.00, 1000000.00, 8.00),
  (1, 3, 5, 320000.00, 0.00, 8.00),
  (1, 4, 3, 1250000.00, 150000.00, 8.00),
  (2, 2, 1, 18900000.00, 500000.00, 8.00),
  (2, 9, 1, 790000.00, 0.00, 8.00),
  (3, 6, 2, 890000.00, 0.00, 8.00),
  (3, 7, 1, 1150000.00, 50000.00, 8.00),
  (4, 5, 4, 3650000.00, 400000.00, 8.00),
  (4, 8, 6, 2450000.00, 600000.00, 8.00),
  (5, 3, 2, 320000.00, 0.00, 8.00),
  (6, 2, 1, 18900000.00, 0.00, 8.00),
  (6, 4, 2, 1250000.00, 100000.00, 8.00),
  (7, 1, 3, 14500000.00, 1500000.00, 8.00),
  (7, 5, 2, 3650000.00, 0.00, 8.00),
  (8, 9, 3, 790000.00, 150000.00, 8.00),
  (8, 3, 4, 320000.00, 0.00, 8.00),
  (9, 8, 2, 2450000.00, 0.00, 8.00),
  (9, 4, 1, 1250000.00, 0.00, 8.00),
  (10, 6, 1, 890000.00, 0.00, 8.00);

INSERT INTO payments (order_id, payment_date, method, amount, status, transaction_ref) VALUES
  (1, '2024-01-12 10:35:00', 'bank_transfer', 35901000.00, 'paid', 'BANK-240112-001'),
  (2, '2024-01-20 15:10:00', 'credit_card', 20725200.00, 'paid', 'CARD-240120-002'),
  (3, '2024-02-03 09:55:00', 'e_wallet', 3145400.00, 'paid', 'EW-240203-003'),
  (4, '2024-02-14 11:40:00', 'bank_transfer', 30629000.00, 'paid', 'BANK-240214-004'),
  (5, '2024-03-08 18:20:00', 'e_wallet', 741200.00, 'refunded', 'EW-240308-005'),
  (6, '2024-03-19 14:10:00', 'credit_card', 23049000.00, 'paid', 'CARD-240319-006'),
  (7, '2024-04-05 08:50:00', 'bank_transfer', 53314000.00, 'pending', 'BANK-240405-007'),
  (8, '2024-04-21 20:25:00', 'e_wallet', 3805000.00, 'paid', 'EW-240421-008'),
  (9, '2024-05-10 15:00:00', 'cash', 6687000.00, 'paid', 'CASH-240510-009');

INSERT INTO shipments (order_id, carrier, tracking_code, shipped_at, delivered_at, shipping_status) VALUES
  (1, 'Giao Hang Nhanh', 'GHN240112001', '2024-01-12 16:00:00', '2024-01-14 09:20:00', 'delivered'),
  (2, 'Nhanh Express', 'NEX240120002', '2024-01-20 17:30:00', '2024-01-21 11:15:00', 'delivered'),
  (3, 'Viettel Post', 'VTP240203003', '2024-02-03 15:00:00', NULL, 'in_transit'),
  (4, 'Giao Hang Tiet Kiem', 'GHTK240214004', '2024-02-14 18:20:00', '2024-02-17 10:00:00', 'delivered'),
  (6, 'Giao Hang Nhanh', 'GHN240319006', '2024-03-19 19:00:00', '2024-03-21 08:45:00', 'delivered'),
  (7, 'Viettel Post', 'VTP240405007', NULL, NULL, 'preparing'),
  (8, 'Nhanh Express', 'NEX240421008', '2024-04-22 09:00:00', '2024-04-23 13:10:00', 'delivered'),
  (9, 'Giao Hang Tiet Kiem', 'GHTK240510009', '2024-05-10 18:00:00', NULL, 'in_transit');

INSERT INTO inventory_movements (product_id, movement_date, movement_type, quantity_change, reference_code, note) VALUES
  (1, '2024-01-02 09:00:00', 'purchase', 25, 'PO-2024-001', 'Nhap dau nam'),
  (2, '2024-01-02 09:10:00', 'purchase', 12, 'PO-2024-001', 'Nhap dau nam'),
  (3, '2024-01-03 10:00:00', 'purchase', 120, 'PO-2024-002', 'Nhap phu kien'),
  (1, '2024-01-12 10:20:00', 'sale', -2, 'ORD-2024-0001', 'Ban hang'),
  (3, '2024-01-12 10:20:00', 'sale', -5, 'ORD-2024-0001', 'Ban hang'),
  (2, '2024-01-20 15:05:00', 'sale', -1, 'ORD-2024-0002', 'Ban hang'),
  (6, '2024-02-03 09:40:00', 'sale', -2, 'ORD-2024-0003', 'Ban hang'),
  (5, '2024-02-14 11:25:00', 'sale', -4, 'ORD-2024-0004', 'Ban hang'),
  (8, '2024-02-14 11:25:00', 'sale', -6, 'ORD-2024-0004', 'Ban hang'),
  (9, '2024-04-22 08:00:00', 'adjustment', -2, 'ADJ-2024-001', 'Hang trung bay hong');

INSERT INTO support_tickets (customer_id, order_id, assigned_employee_id, ticket_code, subject, priority, status, created_at, resolved_at) VALUES
  (1, 1, 5, 'TCK-2024-0001', 'Yeu cau xuat hoa don VAT', 'medium', 'resolved', '2024-01-12 13:00:00', '2024-01-12 15:30:00'),
  (2, 2, 6, 'TCK-2024-0002', 'Can huong dan bao hanh laptop', 'low', 'closed', '2024-01-22 09:10:00', '2024-01-23 10:00:00'),
  (3, 3, 6, 'TCK-2024-0003', 'Kiem tra don hang dang giao', 'medium', 'in_progress', '2024-02-05 14:20:00', NULL),
  (5, 5, 5, 'TCK-2024-0004', 'Hoan tien don hang da huy', 'high', 'resolved', '2024-03-09 08:30:00', '2024-03-10 11:15:00'),
  (7, 7, 5, 'TCK-2024-0005', 'Can doi lich giao hang', 'urgent', 'open', '2024-04-05 16:45:00', NULL),
  (6, 6, 6, 'TCK-2024-0006', 'Hoi ve chuong trinh khach VIP', 'low', 'closed', '2024-03-20 12:00:00', '2024-03-20 15:00:00');

CREATE OR REPLACE VIEW v_order_summary AS
SELECT
  o.order_id,
  o.order_code,
  o.order_date,
  o.status AS order_status,
  o.channel,
  c.customer_code,
  c.full_name AS customer_name,
  c.city AS customer_city,
  c.segment AS customer_segment,
  e.employee_code AS sales_employee_code,
  e.full_name AS sales_employee_name,
  COUNT(oi.order_item_id) AS item_count,
  SUM(oi.quantity) AS total_quantity,
  ROUND(SUM((oi.quantity * oi.unit_price) - oi.discount_amount), 2) AS subtotal_amount,
  ROUND(SUM(((oi.quantity * oi.unit_price) - oi.discount_amount) * oi.tax_rate / 100), 2) AS tax_amount,
  o.shipping_fee,
  ROUND(
    SUM((oi.quantity * oi.unit_price) - oi.discount_amount)
    + SUM(((oi.quantity * oi.unit_price) - oi.discount_amount) * oi.tax_rate / 100)
    + o.shipping_fee,
    2
  ) AS total_amount
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN employees e ON e.employee_id = o.sales_employee_id
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY
  o.order_id,
  o.order_code,
  o.order_date,
  o.status,
  o.channel,
  c.customer_code,
  c.full_name,
  c.city,
  c.segment,
  e.employee_code,
  e.full_name,
  o.shipping_fee;
