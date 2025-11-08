CREATE TABLE `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_type` ENUM('QUIE_STUDENT', 'REGULAR') NOT NULL DEFAULT 'REGULAR',
  `identifier` VARCHAR(128) NOT NULL,
  `password` VARCHAR(255) NOT NULL, -- Added password field for login
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uk_identifier` (`identifier` ASC)
);

CREATE TABLE `ticket_types` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(50) NOT NULL,
  `price` DECIMAL(10, 2) NOT NULL,
  `description` VARCHAR(255) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`)
);

CREATE TABLE `orders` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `order_sn` VARCHAR(64) NOT NULL,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `status` ENUM('COMPLETED') NOT NULL DEFAULT 'COMPLETED',
  `total_amount` DECIMAL(10, 2) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
);

CREATE TABLE `order_details` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `order_id` BIGINT UNSIGNED NOT NULL,
  `ticket_type_id` INT UNSIGNED NOT NULL,
  `quantity` INT UNSIGNED NOT NULL,
  `unit_price` DECIMAL(10, 2) NOT NULL,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`),
  FOREIGN KEY (`ticket_type_id`) REFERENCES `ticket_types` (`id`)
);

INSERT INTO `ticket_types` (`name`, `price`, `description`) VALUES
('QUIE本校学生票', 0.00, '凭本校有效学生证免费入园'),
('校外成人票', 250.00, '适用于所有校外成人游客'),
('校外学生票', 150.00, '适用于所有校外学生游客，需出示有效学生证'),
('家庭票', 600.00, '包含2名成人和2名学生的家庭套票'),
('团体票', 2000.00, '适用于10人及以上的团体游客，需提前预约'),
('年票', 800.00, '全年无限次入园，适用于个人游客'),
('老年票', 100.00, '适用于60岁及以上的老年游客，需出示有效身份证件'),
('儿童票', 100.00, '适用于3-12岁的儿童游客，需出示有效身份证件');
