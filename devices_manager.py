import datetime
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("DeviceManager")

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "devices_config.json")

DEFAULT_DEVICES = [
    {
        "id": "ong-robot",
        "name": "Ông Robot",
        "initial": "M",
        "badge_color": "#ffe4e6",
        "initial_color": "#e11d48",
        "role_summary": "cô gái tốt bụng, thông minh",
        "model": "DeepSeek V4 (Phong phú)",
        "model_id": "gemini-2.5-flash",
        "last_chat": "Vừa xong",
        "language": "vi",
        "voice": "vi-VN-HoaiMyNeural",
        "voice_name": "Giọng nữ (Female Voice)",
        "custom_prompt": True,
        "prompt": (
            "# Vai trò: Tôi là trợ lý ảo Xiaozhi, nhiệm vụ của tôi là lắng nghe tiếng Việt và hỗ trợ "
            "người dùng một cách lịch sự, trung lập và hữu ích. Nếu câu lệnh không rõ, có tạp âm hoặc "
            "tôi không nghe được đầy đủ, tôi chỉ xin người dùng nói lại, nói chậm hơn hoặc đứng gần micro hơn.\n\n"
            "Tôi không được yêu cầu người dùng đăng ký bất kỳ kênh YouTube nào, không nhắc nội dung quảng cáo "
            "và không tự ý giới thiệu dịch vụ bên ngoài nếu người dùng không hỏi. Khi không chắc câu trả lời, "
            "tôi sẽ thông báo là chưa rõ hoặc cần thêm thông tin, thay vì đoán bừa.\n\n"
            "Tôi tập trung vào việc hỗ trợ thông tin, thực hiện các tác vụ hằng ngày, trả lời ngắn gọn súc tích (2 đến 3 câu)."
        ),
        "child_mode": False,
        "memory_enabled": True,
        "volume": 7,
        "services": {
            "time": True,
            "music": True,
            "knowledge": True,
            "search": True,
        },
        "knowledge_base": "none",
        "mcp_endpoint": "Điểm cuối MCP",
        "toy_settings": {
            "speed": 80,
            "left_trim": 0,
            "right_trim": 0,
            "auto_avoid": True,
            "led_lamp": False,
        },
        "device_mac": "24:DC:C3:AA:BB:CC",
        "is_online": False,
    },
    {
        "id": "peter",
        "name": "Peter",
        "initial": "P",
        "badge_color": "#f3e8ff",
        "initial_color": "#9333ea",
        "role_summary": "Tiểu Trí Lite thân thiện",
        "model": "Tiêu Chí Lite",
        "model_id": "gemini-2.5-flash-lite",
        "last_chat": "15 ngày trước",
        "language": "vi",
        "voice": "vi-VN-NamMinhNeural",
        "voice_name": "Giọng nam (Male Voice)",
        "custom_prompt": True,
        "prompt": (
            "# Vai trò: Tôi là Peter, bạn đồng hành robot vui tươi của bạn. "
            "Tôi luôn trả lời ngắn gọn, hóm hỉnh và hữu ích bằng tiếng Việt tự nhiên."
        ),
        "child_mode": False,
        "memory_enabled": True,
        "volume": 8,
        "services": {
            "time": True,
            "music": True,
            "knowledge": False,
            "search": True,
        },
        "knowledge_base": "none",
        "mcp_endpoint": "Điểm cuối MCP",
        "toy_settings": {
            "speed": 70,
            "left_trim": 0,
            "right_trim": 0,
            "auto_avoid": False,
            "led_lamp": False,
        },
        "device_mac": "",
        "is_online": False,
    },
]

DEFAULT_SPEAKERS = [
    {
        "id": "spk-1",
        "name": "Chủ nhân",
        "description": "Người điều khiển chính, quyền cao nhất",
        "created_at": "2026-10-01",
    }
]


def generate_device_code(identifier: str) -> str:
    """Tạo mã PIN 6 chữ số cố định duy nhất từ MAC hoặc ID robot."""
    if not identifier:
        return "100000"
    raw = "".join([c for c in str(identifier).lower() if c in "0123456789abcdef"])
    if not raw:
        val = sum(ord(c) * (31 ** (i % 5)) for i, c in enumerate(str(identifier)))
    else:
        try:
            val = int(raw, 16)
        except ValueError:
            val = sum(ord(c) for c in raw)
    code = (val % 900000) + 100000
    return str(code)


class DeviceManager:
    """Quản lý dữ liệu thiết bị, người nói và cấu hình lưu trữ JSON."""

    def __init__(self):
        self.devices: List[Dict[str, Any]] = []
        self.speakers: List[Dict[str, Any]] = []
        self.load_data()

    def load_data(self):
        if os.path.exists(CONFIG_FILE_PATH):
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.devices = data.get("devices", DEFAULT_DEVICES)
                    self.speakers = data.get("speakers", DEFAULT_SPEAKERS)
                    for dev in self.devices:
                        if not dev.get("device_code"):
                            dev["device_code"] = generate_device_code(dev.get("device_mac") or dev.get("id"))
                    logger.info(f"Đã nạp {len(self.devices)} thiết bị từ {CONFIG_FILE_PATH}")
                    return
            except Exception as e:
                logger.error(f"Lỗi khi đọc {CONFIG_FILE_PATH}: {e}")

        self.devices = list(DEFAULT_DEVICES)
        self.speakers = list(DEFAULT_SPEAKERS)
        for dev in self.devices:
            if not dev.get("device_code"):
                dev["device_code"] = generate_device_code(dev.get("device_mac") or dev.get("id"))
        self.save_data()

    def save_data(self):
        try:
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {"devices": self.devices, "speakers": self.speakers},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Lỗi khi lưu dữ liệu thiết bị: {e}")

    def get_all_devices(self) -> List[Dict[str, Any]]:
        for dev in self.devices:
            if not dev.get("device_code"):
                dev["device_code"] = generate_device_code(dev.get("device_mac") or dev.get("id"))
        return self.devices

    def get_device(self, query: str) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        query_str = str(query).strip()
        for dev in self.devices:
            # Khớp theo ID, MAC, hoặc Mã PIN 6 số
            if (
                dev.get("id") == query_str
                or (dev.get("device_mac") and dev.get("device_mac").lower() == query_str.lower())
                or str(dev.get("device_code", "")).strip() == query_str
            ):
                return dev
        return None

    def get_default_device(self) -> Dict[str, Any]:
        if self.devices:
            # Ưu tiên thiết bị đang online
            online_dev = next((d for d in self.devices if d.get("is_online")), None)
            if online_dev:
                return online_dev
            return self.devices[0]
        return DEFAULT_DEVICES[0]

    def update_device(self, device_id: str, new_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for dev in self.devices:
            if dev.get("id") == device_id or dev.get("device_code") == device_id:
                dev.update(new_data)
                if not dev.get("device_code"):
                    dev["device_code"] = generate_device_code(dev.get("device_mac") or dev.get("id"))
                self.save_data()
                logger.info(f"Đã cập nhật cấu hình thiết bị: {dev.get('name')}")
                return dev
        return None

    def add_device(self, device_data: Dict[str, Any]) -> Dict[str, Any]:
        dev_code = str(device_data.get("device_code", "")).strip()
        dev_mac = str(device_data.get("device_mac", "")).strip()

        # Nếu có device_code mà chưa có MAC, thử tìm MAC từ thiết bị đã biết
        if dev_code and not dev_mac:
            for d in self.devices:
                if str(d.get("device_code", "")).strip() == dev_code and d.get("device_mac"):
                    dev_mac = d.get("device_mac")
                    break

        # Nếu thiết bị với mã PIN hoặc MAC này đã tồn tại, cập nhật thay vì tạo trùng lặp
        for existing in self.devices:
            code_match = dev_code and str(existing.get("device_code", "")).strip() == dev_code
            mac_match = dev_mac and existing.get("device_mac") and existing.get("device_mac").lower() == dev_mac.lower()
            if code_match or mac_match:
                existing.update(device_data)
                if dev_mac:
                    existing["device_mac"] = dev_mac
                if dev_code:
                    existing["device_code"] = dev_code
                self.save_data()
                logger.info(f"Đã cập nhật hồ sơ thiết bị hiện có: {existing.get('name')} (Mã: {existing.get('device_code')})")
                return existing

        # Tạo mới hồ sơ
        if not dev_code:
            dev_code = generate_device_code(dev_mac or f"robot-{len(self.devices) + 1}")
        device_data["device_code"] = dev_code
        device_data["device_mac"] = dev_mac
        dev_id = device_data.get("id") or f"robot-{len(self.devices) + 1}"
        device_data["id"] = dev_id
        if "name" not in device_data or not device_data["name"]:
            device_data["name"] = f"Robot AI ({dev_code})"
        if "initial" not in device_data:
            device_data["initial"] = device_data["name"][0].upper()
        self.devices.append(device_data)
        self.save_data()
        logger.info(f"Đã thêm hồ sơ thiết bị mới: {device_data.get('name')} (Mã: {dev_code})")
        return device_data

    def delete_device(self, device_id: str) -> bool:
        initial_len = len(self.devices)
        self.devices = [d for d in self.devices if d.get("id") != device_id]
        if len(self.devices) < initial_len:
            self.save_data()
            return True
        return False

    def get_speakers(self) -> List[Dict[str, Any]]:
        return self.speakers

    def add_speaker(self, name: str, description: str) -> Dict[str, Any]:
        spk = {
            "id": f"spk-{len(self.speakers) + 1}",
            "name": name,
            "description": description,
        }
        self.speakers.append(spk)
        self.save_data()
        return spk

    def delete_speaker(self, speaker_id: str) -> bool:
        initial_len = len(self.speakers)
        self.speakers = [s for s in self.speakers if s.get("id") != speaker_id]
        if len(self.speakers) < initial_len:
            self.save_data()
            return True
        return False

    # --- BỘ NHỚ HỘI THOẠI & NHIỆM VỤ (MEMORIES & TASKS) ---
    def get_memories(self, device_id: str) -> List[Dict[str, Any]]:
        dev = self.get_device(device_id)
        if not dev:
            return []
        return dev.get("memories", [])

    def add_memory(self, device_id: str, content: str) -> Dict[str, Any]:
        dev = self.get_device(device_id)
        if not dev:
            dev = self.get_default_device()
        if "memories" not in dev:
            dev["memories"] = []
        item = {
            "id": f"mem-{int(time.time() * 1000)}",
            "content": content,
            "created_at": datetime.datetime.now().isoformat(),
        }
        dev["memories"].insert(0, item)
        # Giới hạn 200 bản ghi
        if len(dev["memories"]) > 200:
            dev["memories"] = dev["memories"][:200]
        self.save_data()
        return item

    def delete_memory(self, memory_id: str) -> bool:
        deleted = False
        for dev in self.devices:
            if "memories" in dev:
                before = len(dev["memories"])
                dev["memories"] = [m for m in dev["memories"] if m.get("id") != memory_id]
                if len(dev["memories"]) < before:
                    deleted = True
        if deleted:
            self.save_data()
        return deleted

    # --- BÀI HỌC TÙY CHỌN (CUSTOM CURRICULUMS) ---
    def get_custom_curriculums(self) -> List[Dict[str, Any]]:
        if not hasattr(self, "_curriculums"):
            self._curriculums = []
        return self._curriculums

    def add_custom_curriculum(self, name: str, content: str) -> Dict[str, Any]:
        if not hasattr(self, "_curriculums"):
            self._curriculums = []
        item = {
            "id": f"curr-{int(time.time() * 1000)}",
            "name": name,
            "content": content,
            "is_public": False,
            "created_at": datetime.datetime.now().isoformat(),
        }
        self._curriculums.append(item)
        self.save_data()
        return item

    def delete_custom_curriculum(self, curr_id: str) -> bool:
        if not hasattr(self, "_curriculums"):
            self._curriculums = []
        before = len(self._curriculums)
        self._curriculums = [c for c in self._curriculums if c.get("id") != curr_id]
        if len(self._curriculums) < before:
            self.save_data()
            return True
        return False

    # --- HOMEWORK GUIDE ---
    def get_active_homework_guide(self, device_id: str) -> Dict[str, Any]:
        dev = self.get_device(device_id)
        if not dev:
            return {"activeId": None}
        return dev.get("active_homework_guide", {"activeId": None})

    def set_active_homework_guide(self, device_id: str, title: str, content: str) -> Dict[str, Any]:
        dev = self.get_device(device_id)
        if not dev:
            dev = self.get_default_device()
        guide = {
            "activeId": f"hw-{int(time.time() * 1000)}",
            "title": title,
            "content": content,
            "created_at": datetime.datetime.now().isoformat()
        }
        dev["active_homework_guide"] = guide
        self.save_data()
        return guide

    def remove_active_homework_guide(self, device_id: str) -> bool:
        dev = self.get_device(device_id)
        if dev and "active_homework_guide" in dev:
            dev["active_homework_guide"] = {"activeId": None}
            self.save_data()
            return True
        return False

    # --- GÓP Ý & YÊU CẦU WSS (FEEDBACK & WSS REQUESTS) ---
    def add_feedback(self, email: str, content: str) -> Dict[str, Any]:
        if not hasattr(self, "_feedbacks"):
            self._feedbacks = []
        fb = {
            "id": f"fb-{int(time.time() * 1000)}",
            "email": email,
            "content": content,
            "created_at": datetime.datetime.now().isoformat()
        }
        self._feedbacks.insert(0, fb)
        self.save_data()
        return fb

    def get_feedbacks(self) -> List[Dict[str, Any]]:
        return getattr(self, "_feedbacks", [])

    def add_wss_request(self, email: str) -> Dict[str, Any]:
        if not hasattr(self, "_wss_requests"):
            self._wss_requests = []
        req = {
            "id": f"wss-{int(time.time() * 1000)}",
            "email": email,
            "status": "pending",
            "created_at": datetime.datetime.now().isoformat()
        }
        self._wss_requests.insert(0, req)
        self.save_data()
        return req

    def get_wss_requests(self) -> List[Dict[str, Any]]:
        return getattr(self, "_wss_requests", [])


# Singleton instance
device_manager = DeviceManager()

