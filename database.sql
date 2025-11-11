CREATE TABLE `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_type` ENUM('QUIE_STUDENT', 'REGULAR') NOT NULL DEFAULT 'REGULAR',
  `phone` VARCHAR(30) NOT NULL,
  `password` VARCHAR(128) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY (`phone`)
);

CREATE TABLE `ticket_types` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(50) NOT NULL,
  `price` DECIMAL(10, 2) NOT NULL,
  `description` VARCHAR(255) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY (`name`)
);

CREATE TABLE `orders` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `status` ENUM('PENDING','COMPLETED','PAID','CANCELLED') NOT NULL DEFAULT 'PENDING',
  `total_amount` DECIMAL(10, 2) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `paid_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON UPDATE CASCADE
);

CREATE TABLE `order_details` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `order_id` BIGINT UNSIGNED NOT NULL,
  `ticket_type_id` INT UNSIGNED NOT NULL,
  `quantity` INT UNSIGNED NOT NULL,
  `unit_price` DECIMAL(10, 2) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `order_id` (`order_id`),
  KEY `ticket_type_id` (`ticket_type_id`),
  FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (`ticket_type_id`) REFERENCES `ticket_types` (`id`) ON UPDATE CASCADE
);

INSERT INTO `ticket_types` (`id`, `name`, `price`, `description`) VALUES
(1, 'QUIE本校学生票', 0.00, '凭本校有效学生证免费入园'),
(2, '校外成人票', 250.00, '适用于所有校外成人游客'),
(3, '校外学生票', 150.00, '适用于所有校外学生游客，需出示有效学生证'),
(4, '家庭票', 600.00, '包含2名成人和2名学生的家庭套票'),
(5, '团体票', 2000.00, '适用于10人及以上的团体游客，需提前预约'),
(6, '年票', 800.00, '全年无限次入园，适用于个人游客'),
(7, '老年票', 100.00, '适用于60岁及以上的老年游客，需出示有效身份证件'),
(8, '儿童票', 100.00, '适用于3-12岁的儿童游客，需出示有效身份证件');