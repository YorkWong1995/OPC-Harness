# 相机 SDK 文档

## 快速开始

### 初始化

使用 `init_camera()` 函数初始化相机：

```python
from camera_sdk import init_camera

camera = init_camera("COM3", baudrate=115200)
```

### 拍照

调用 `capture()` 方法拍照：

```python
image = camera.capture()
```

## 常见问题

**Q: 如何设置波特率？**
A: 在 init_camera 时传入 baudrate 参数。

**Q: 支持哪些串口？**
A: 支持 COM1-COM9 (Windows) 和 /dev/ttyUSB* (Linux)。
