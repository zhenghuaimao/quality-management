SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `UsersRecord`;
CREATE TABLE `UsersRecord` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增id',
  `name` varchar(150) DEFAULT NULL COMMENT '姓名',
  `email` varchar(150) DEFAULT NULL COMMENT '邮箱',
  `password` varchar(150) DEFAULT NULL COMMENT '密码',
  `status` INT DEFAULT 1 COMMENT '状态，0-未激活，1-激活，2-冻结',
  `role` varchar(120) DEFAULT NULL COMMENT '角色',
  `createdTime` datetime COMMENT '账号创建时间',
  `updateTime` datetime COMMENT '账号修改标志',
  `isDelete` BOOL DEFAULT FALSE COMMENT '软删除标志',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10020 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户管理';

SET FOREIGN_KEY_CHECKS = 1;