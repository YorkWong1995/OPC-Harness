"""测试 Python 文件"""

def init_camera(port: str, baudrate: int = 9600):
    """初始化相机连接

    Args:
        port: 串口号，如 "COM3"
        baudrate: 波特率，默认 9600

    Returns:
        Camera 对象
    """
    print(f"正在连接相机 {port}...")
    return Camera(port, baudrate)

class Camera:
    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate

    def capture(self):
        """拍摄照片"""
        return "image.jpg"
