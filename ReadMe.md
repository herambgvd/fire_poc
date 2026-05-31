# Fire & Smoke Detection System

## Overview

This project is a real-time fire and smoke detection system developed for Digital Image Processing. The system monitors video input from local test videos or IP-based CCTV camera streams and detects possible fire or smoke incidents using a two-stage deep learning pipeline.

The application is designed to work as a low-resource, CPU-friendly monitoring system using YOLOv11n and MobileNetV3. It includes a Python-based GUI dashboard, live video monitoring, alert history, confidence scores, system logs, alert sound, and automatic evidence video generation.

---

## Team Members

* Arfa Riaz
* Waqas Ul Hasan

Original team repository: https://github.com/waqasuh/DIP-Project

---

## Key Features

* Real-time fire and smoke detection
* Support for local test videos
* Support for IP-based CCTV camera streams
* Two-stage detection pipeline
* YOLOv11n-based detection model
* MobileNetV3-based classification/confirmation model
* Python GUI dashboard
* Alert history with confidence scores
* System logging
* Alert sound notification
* Automatic evidence video generation
* Low-resource CPU-focused design

---

## Detection Pipeline

The system uses a two-stage detection process:

```text
Video Source
     ↓
Frame Capture
     ↓
Stage 1: MobileNetV3 Screening
     ↓
Stage 2: YOLOv11n Confirmation
     ↓
Alert Generation
     ↓
Evidence Video + Logs
```

Stage 1 performs lightweight screening to detect possible danger frames. Stage 2 confirms the threat using a more detailed object detection model. This approach reduces unnecessary processing and helps the system run efficiently on limited resources.

---

## Dataset and Model Training

The dataset was collected and combined by the team using Roboflow. The models were trained and tested using Google Colab GPU resources.

Models used:

* YOLOv11n for fire/smoke detection
* MobileNetV3 Small for lightweight classification/screening

The system was designed with practical CCTV-based monitoring in mind, especially for environments where GPU resources may not be available during deployment.

---

## Application Structure

```text
Application/
│
├── main.py
├── config.py
├── logging_config.py
├── requirements.txt
├── settings.json
├── alert_sound.mp3
├── camera/
├── core/
├── gui/
├── alerts/
├── evidence/
├── logs/
├── mobilenetv3_small_stage1_with_normal.pth
└── yolon11_stage2_with_normal.pt
```

---

## How to Run

### 1. Navigate to the project folder

```bash
cd Application
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the application

```bash
python main.py
```

Alternative command from the root folder:

```bash
python Application/main.py
```

---

## How to Use

After launching the GUI dashboard:

1. Click **Test Video** to select a local video file, or add an IP camera URL from **Settings**.
2. Click **Start Monitoring**.
3. The system loads Stage 1 and Stage 2 models.
4. The video feed appears on the dashboard.
5. Detection logs appear in the System Logs panel.
6. Confirmed fire or smoke incidents are saved in Alert History.
7. The system plays an alert sound and generates evidence video.

---

## Technologies Used

* Python
* OpenCV
* YOLOv11n
* MobileNetV3
* PyTorch
* Roboflow
* Google Colab
* GUI-based desktop application
* Digital Image Processing techniques

---


## Future Improvements

* Convert the Python application into an executable `.exe`
* Improve model accuracy using more diverse CCTV fire/smoke data
* Add support for more simultaneous CCTV feeds
* Add cloud-based alert storage
* Deploy on edge devices for real-time monitoring

---

## Author

Arfa Riaz
BS Computer Science
COMSATS University Islamabad, Lahore Campus
