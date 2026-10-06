CREATE DATABASE IF NOT EXISTS taskmanager;
USE taskmanager;

CREATE TABLE IF NOT EXISTS tasks (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  title      VARCHAR(150) NOT NULL,
  category   ENUM('task', 'exam') NOT NULL DEFAULT 'task',
  priority   ENUM('high', 'medium', 'low') NOT NULL DEFAULT 'medium',
  due_date   DATE NULL,
  remind_at  DATETIME NULL,
  is_done    TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);