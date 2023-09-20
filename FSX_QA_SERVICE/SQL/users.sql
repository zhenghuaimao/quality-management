SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增id',
  `username` varchar(150) DEFAULT NULL COMMENT '用户名',
  `email` varchar(150) DEFAULT NULL COMMENT '邮箱',
  `password` varchar(150) DEFAULT NULL COMMENT '密码',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10020 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='应用管理';

SET FOREIGN_KEY_CHECKS = 1;