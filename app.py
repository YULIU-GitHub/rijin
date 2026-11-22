"""日进 · 每日任务进度管理 —— 应用入口。"""
from __future__ import annotations

import argparse
import ctypes
import logging
import sys
from logging.handlers import RotatingFileHandler

from PyQt5.QtCore import QLocale, QObject, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import QApplication, QMessageBox

from rijin import APP_ID, APP_NAME, __version__
from rijin.app_controller import AppController
from rijin.core.config import Config
from rijin.core.database import Database
from rijin.core.paths import (
    assets_dir,
    config_path,
    data_dir,
    database_path,
    ensure_data_dirs,
    log_dir,
)
from rijin.core.repository import Repository
from rijin.ui import icons, theme

LOGGER = logging.getLogger(__name__)
SERVER_NAME = "RiJin.DailyTasks.SingleInstance.v1"


class SingleInstance(QObject):
    commandReceived = pyqtSignal(str)

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept)
        QLocalServer.removeServer(SERVER_NAME)
        if not self.server.listen(SERVER_NAME):
            QLocalServer.removeServer(SERVER_NAME)
            self.server.listen(SERVER_NAME)

    def _accept(self) -> None:
        while self.server.hasPendingConnections():
            connection = self.server.nextPendingConnection()
            if connection is None:
                continue
            connection.readyRead.connect(lambda conn=connection: self._read(conn))
            QTimer.singleShot(100, lambda conn=connection: self._read(conn))

    def _read(self, connection: QLocalSocket) -> None:
        try:
            data = bytes(connection.readAll()).decode("utf-8", errors="ignore").strip()
            if data:
                self.commandReceived.emit(data)
        except RuntimeError:
            pass
        finally:
            try:
                connection.disconnectFromServer()
                connection.deleteLater()
            except RuntimeError:
                pass

    def close(self) -> None:
        self.server.close()
        QLocalServer.removeServer(SERVER_NAME)


def setup_logging(debug: bool = False) -> None:
    ensure_data_dirs()
    handlers = [
        RotatingFileHandler(
            str(log_dir() / "app.log"),
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    ]
    if debug and sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def install_exception_hook() -> None:
    def hook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        LOGGER.critical("未捕获异常", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = hook


def _set_windows_app_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _command_from_args(args: argparse.Namespace) -> str:
    if args.add:
        return "add"
    if args.center:
        return "center"
    if args.settings:
        return "settings"
    return "show"


def _send_to_running(command: str) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(350):
        return False
    socket.write(command.encode("utf-8"))
    socket.waitForBytesWritten(350)
    socket.disconnectFromServer()
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="日进", description="每日任务进度管理")
    parser.add_argument("--add", action="store_true", help="启动后打开新建任务")
    parser.add_argument("--center", action="store_true", help="启动后打开任务中心")
    parser.add_argument("--settings", action="store_true", help="启动后打开设置")
    parser.add_argument("--minimized", action="store_true", help="仅显示悬浮窗（默认行为）")
    parser.add_argument("--reset-position", action="store_true", help="重置窗口位置")
    parser.add_argument("--debug", action="store_true", help="输出调试日志")
    parser.add_argument("--version", action="store_true", help="显示版本")
    args = parser.parse_args(argv)

    if args.version:
        print("日进 %s" % __version__)
        return 0

    setup_logging(args.debug)
    install_exception_hook()
    _set_windows_app_id()

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("RiJin")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(icons.app_icon())
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    QLocale.setDefault(QLocale(QLocale.Chinese, QLocale.China))
    app.setFont(QFont("Microsoft YaHei UI", 9))
    app.setStyleSheet(theme.stylesheet(assets_dir()))

    if _send_to_running(_command_from_args(args)):
        return 0

    ensure_data_dirs()
    first_run = not database_path().exists()
    config = Config(config_path())
    if args.reset_position:
        config.set("floating_pos", None)
        config.set("center_pos", None)
        config.save()
    try:
        database = Database(database_path())
        repository = Repository(database)
    except Exception as exc:
        LOGGER.exception("数据库初始化失败")
        QMessageBox.critical(
            None,
            "日进无法启动",
            "任务数据库无法打开：\n%s\n\n请检查数据目录权限：%s" % (exc, data_dir()),
        )
        return 1

    controller = AppController(app, config, database, repository)
    controller.first_run = first_run
    instance = SingleInstance()
    instance.commandReceived.connect(controller.handle_command)
    app.aboutToQuit.connect(controller.shutdown)
    controller.start()

    command = _command_from_args(args)
    if command == "add":
        QTimer.singleShot(500, controller.open_add)
    elif command == "center":
        QTimer.singleShot(500, lambda: controller.open_center("today"))
    elif command == "settings":
        QTimer.singleShot(500, controller.open_settings)

    exit_code = app.exec_()
    instance.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
