#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
番茄钟计时器 - 系统托盘版
支持在托盘图标上显示倒计时、状态变色、右键菜单控制
"""

import time
import threading
import math

from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import MenuItem as Item, Menu

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

# ==================== 配置 ====================

# 时间设置（单位：分钟）
WORK_TIME = 25
BREAK_TIME = 5
LONG_BREAK_TIME = 15
ROUNDS_BEFORE_LONG_BREAK = 4

# 界面颜色设置（三种状态色）
WORK_COLOR = (231, 76, 60)            # 工作时间 (红色)
BREAK_COLOR = (39, 174, 96)           # 休息时间 (绿色)
PAUSE_COLOR = (149, 165, 166)         # 暂停状态 (灰色)

# 通知设置
ENABLE_NOTIFICATIONS = True

# 图标显示设置
SHOW_SECONDS = True
ICON_SIZE = 256
LARGE_ICON_TEXT_SIZE = 180
LARGE_ICON_STATE_SIZE = 36

# 自动循环设置
AUTO_START_NEXT = True

# ==================== 图标生成器 ====================

class IconGenerator:
    """图标生成器 - 生成圆润方形图标"""

    def __init__(self, size=ICON_SIZE):
        self.size = size

    def create_icon(self, time_text, color, state_text=""):
        """创建带文字的图标"""
        img = Image.new('RGBA', (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        padding = 4
        corner_radius = 16

        self._draw_rounded_rect(draw, padding, padding,
                                self.size - padding, self.size - padding,
                                corner_radius, color)

        try:
            font = ImageFont.truetype("ariblk.ttf", LARGE_ICON_TEXT_SIZE)
        except:
            try:
                font = ImageFont.truetype("impact.ttf", LARGE_ICON_TEXT_SIZE)
            except:
                try:
                    font = ImageFont.truetype("msyh.ttc", LARGE_ICON_TEXT_SIZE)
                except:
                    try:
                        font = ImageFont.truetype("arial.ttf", LARGE_ICON_TEXT_SIZE)
                    except:
                        font = ImageFont.load_default()

        try:
            small_font = ImageFont.truetype("msyh.ttc", LARGE_ICON_STATE_SIZE)
        except:
            try:
                small_font = ImageFont.truetype("arial.ttf", LARGE_ICON_STATE_SIZE)
            except:
                small_font = ImageFont.load_default()

        if time_text:
            draw.text((self.size // 2, self.size // 2), time_text,
                     fill=(255, 255, 255, 255), font=font, anchor='mm')

        if state_text:
            draw.text((self.size // 2, self.size - 40), state_text,
                     fill=(255, 255, 255, 200), font=small_font, anchor='mm')

        return img

    def _draw_rounded_rect(self, draw, x1, y1, x2, y2, radius, color):
        """绘制圆角矩形"""
        if isinstance(color, tuple) and len(color) == 3:
            color = color + (255,)

        draw.arc((x1, y1, x1 + radius * 2, y1 + radius * 2), 180, 270, fill=color)
        draw.arc((x2 - radius * 2, y1, x2, y1 + radius * 2), 270, 360, fill=color)
        draw.arc((x1, y2 - radius * 2, x1 + radius * 2, y2), 90, 180, fill=color)
        draw.arc((x2 - radius * 2, y2 - radius * 2, x2, y2), 0, 90, fill=color)

        draw.rectangle((x1 + radius, y1, x2 - radius, y2), fill=color)
        draw.rectangle((x1, y1 + radius, x2, y2 - radius), fill=color)

        draw.rectangle((x1, y1, x1 + radius, y1 + radius), fill=color)
        draw.rectangle((x2 - radius, y1, x2, y1 + radius), fill=color)
        draw.rectangle((x1, y2 - radius, x1 + radius, y2), fill=color)
        draw.rectangle((x2 - radius, y2 - radius, x2, y2), fill=color)


# ==================== 番茄钟主类 ====================

class PomodoroTimer:
    """番茄钟计时器主类"""

    STATE_WORK = 'work'
    STATE_BREAK = 'break'
    STATE_LONG_BREAK = 'long_break'
    STATE_PAUSED = 'paused'

    def __init__(self):
        self.icon_gen = IconGenerator(ICON_SIZE)

        self.current_state = self.STATE_WORK
        self.previous_state = None
        self.is_running = False
        self.is_paused = False
        self.current_time = WORK_TIME * 60
        self.rounds_completed = 0

        self.tray_icon = None
        self.timer_thread = None
        self.running = True

        self.colors = {
            self.STATE_WORK: WORK_COLOR,
            self.STATE_BREAK: BREAK_COLOR,
            self.STATE_LONG_BREAK: BREAK_COLOR,
            self.STATE_PAUSED: PAUSE_COLOR,
        }

    def format_time(self, seconds=None):
        """格式化时间显示"""
        if seconds is None:
            seconds = self.current_time

        minutes = seconds // 60
        secs = seconds % 60

        if SHOW_SECONDS:
            return f"{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}"

    def get_time_text(self):
        """获取图标上显示的时间文本"""
        minutes = math.ceil(self.current_time / 60)
        if not self.is_running or self.is_paused:
            return "P"
        return f"{minutes:02d}"

    def get_color(self):
        """获取当前状态对应的颜色"""
        if self.is_paused:
            return PAUSE_COLOR
        return self.colors.get(self.current_state, WORK_COLOR)

    def get_state_text(self):
        """获取状态文本"""
        if self.is_paused:
            return "已暂停"
        state_map = {
            self.STATE_WORK: "工作中",
            self.STATE_BREAK: "休息中",
            self.STATE_LONG_BREAK: "长休息",
        }
        return state_map.get(self.current_state, "")

    def create_tray_icon(self):
        """创建托盘图标"""
        state = self.get_state_text()
        time_detail = self.format_time()
        state_text = f"{state} {time_detail}"

        icon = self.icon_gen.create_icon(
            self.get_time_text(),
            self.get_color(),
            state_text
        )
        return icon

    def update_icon(self):
        """更新托盘图标"""
        if self.tray_icon:
            self.tray_icon.icon = self.create_tray_icon()
            self.tray_icon.title = f"番茄钟 - {self.get_state_text()} {self.format_time()}"

    def show_notification(self, title, message):
        """显示系统通知"""
        if not ENABLE_NOTIFICATIONS:
            return

        try:
            if PLYER_AVAILABLE:
                notification.notify(
                    title=title,
                    message=message,
                    timeout=10
                )
        except Exception as e:
            print(f"通知发送失败: {e}")

    def timer_tick(self):
        """计时器滴答"""
        while self.running:
            if self.is_running and not self.is_paused:
                if self.current_time > 0:
                    self.current_time -= 1
                    self.update_icon()
                    time.sleep(1)
                else:
                    self.timer_finished()
            else:
                time.sleep(0.1)

    def timer_finished(self):
        """计时完成处理"""
        self.is_running = False

        if self.current_state == self.STATE_WORK:
            self.rounds_completed += 1

            if self.rounds_completed % ROUNDS_BEFORE_LONG_BREAK == 0:
                self.switch_state(self.STATE_LONG_BREAK)
                self.show_notification(
                    "工作时间结束！",
                    f"已完成 {self.rounds_completed} 轮，开始长休息 {LONG_BREAK_TIME} 分钟！"
                )
            else:
                self.switch_state(self.STATE_BREAK)
                self.show_notification(
                    "工作时间结束！",
                    f"已完成 {self.rounds_completed} 轮，开始休息 {BREAK_TIME} 分钟！"
                )
        else:
            self.switch_state(self.STATE_WORK)
            self.show_notification(
                "休息结束！",
                "开始新的番茄工作时间！"
            )

        self.update_icon()

        if AUTO_START_NEXT:
            self.start()

    def switch_state(self, new_state):
        """切换状态"""
        self.current_state = new_state

        if new_state == self.STATE_WORK:
            self.current_time = WORK_TIME * 60
        elif new_state == self.STATE_BREAK:
            self.current_time = BREAK_TIME * 60
        elif new_state == self.STATE_LONG_BREAK:
            self.current_time = LONG_BREAK_TIME * 60

    def start(self):
        """开始计时"""
        if self.is_paused:
            self.is_paused = False
            self.current_state = self.previous_state or self.STATE_WORK
        else:
            self.is_running = True

        self.update_icon()

    def pause(self):
        """暂停计时"""
        if self.is_running:
            self.previous_state = self.current_state
            self.is_paused = True
            self.update_icon()

    def toggle(self):
        """切换开始/暂停"""
        if self.is_running and not self.is_paused:
            self.pause()
        else:
            self.start()

    def next_round(self):
        """下一轮"""
        if self.current_state == self.STATE_WORK:
            self.timer_finished()
        else:
            self.switch_state(self.STATE_WORK)
            self.start()

    def reset(self):
        """重置当前轮时间"""
        self.is_paused = False
        self.switch_state(self.current_state)
        self.update_icon()

    def show_config(self, icon, item):
        """右键查看当前配置"""
        import ctypes
        msg = (
            f"工作时间: {WORK_TIME} 分钟\n"
            f"休息时间: {BREAK_TIME} 分钟\n"
            f"长休息: {LONG_BREAK_TIME} 分钟\n"
            f"长休息间隔: {ROUNDS_BEFORE_LONG_BREAK} 轮\n"
            f"显示秒数: {'是' if SHOW_SECONDS else '否'}\n"
            f"自动下一轮: {'是' if AUTO_START_NEXT else '否'}\n"
            f"通知: {'开' if ENABLE_NOTIFICATIONS else '关'}"
        )
        threading.Thread(
            target=lambda: ctypes.windll.user32.MessageBoxW(0, msg, "当前配置", 0),
            daemon=True
        ).start()

    def create_menu(self):
        """创建托盘菜单"""
        def get_status_text(s):
            if self.is_running and not self.is_paused:
                return "暂停"
            else:
                return "开始"

        return Menu(
            Item(get_status_text, lambda _: self.toggle(), default=True),
            Item("下一轮", lambda _: self.next_round()),
            Item("重置", lambda _: self.reset()),
            Menu.SEPARATOR,
            Item("查看配置", self.show_config),
            Item("退出", lambda _: self.quit())
        )

    def run(self):
        """运行应用"""
        self.tray_icon = pystray.Icon(
            "pomodoro",
            self.create_tray_icon(),
            "番茄钟",
            self.create_menu()
        )

        self.timer_thread = threading.Thread(target=self.timer_tick, daemon=True)
        self.timer_thread.start()

        try:
            self.tray_icon.run()
        except Exception as e:
            print(f"托盘运行错误: {e}")

    def quit(self):
        """退出应用"""
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()


def install_dependencies():
    """检查并提示安装依赖"""
    missing = []

    try:
        import pystray
    except ImportError:
        missing.append('pystray')

    try:
        from PIL import Image
    except ImportError:
        missing.append('Pillow')

    try:
        from plyer import notification
    except ImportError:
        missing.append('plyer')

    if missing:
        print(f"请安装以下依赖: pip install {' '.join(missing)}")
        return False
    return True


if __name__ == '__main__':
    if install_dependencies():
        app = PomodoroTimer()
        app.run()
