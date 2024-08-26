import io
import os
from flask import Flask, Response, send_file, jsonify
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
import cv2
from flask_cors import CORS
from threading import Thread
import time


app = Flask(__name__)
CORS(app)

# Configurar la cámara
camera = Picamera2()
camera.configure(camera.create_preview_configuration(main={"format": 'XRGB8888', "size": (640, 480)}))
camera.start()

recording = False
recording_thread = None

def generate_frames():
    while True:
        frame = camera.capture_array()
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/capture_photo')
def capture_photo():
    frame = camera.capture_array()
    ret, buffer = cv2.imencode('.jpg', frame)
    io_buf = io.BytesIO(buffer)
    return send_file(io_buf, mimetype='image/jpeg', as_attachment=True, download_name='photo.jpg')

def record_video(filename, duration):
    global recording
    recording = True

    try:
        # Detener la cámara antes de configurar la grabación de video
        print("Stopping camera for reconfiguration.")
        camera.stop()
        video_config = camera.create_video_configuration(main={"size": (640, 480)})
        camera.configure(video_config)
        camera.start()
        encoder = H264Encoder()
        print(f"Starting recording to {filename}.")
        camera.start_recording(encoder, filename)

        start_time = time.time()
        while time.time() - start_time < duration:
            if not recording:
                break
            time.sleep(0.1)  # Pequeña espera para reducir la carga del CPU

        print("Stopping recording.")
        camera.stop_recording()
        print("Restarting camera for streaming.")
        camera.start()  # Reiniciar la cámara para el streaming
        recording = False
    except Exception as e:
        print(f"Error during recording: {e}")
        recording = False

@app.route('/start_recording', methods=['POST'])
def start_recording():
    global recording_thread

    if recording:
        return jsonify({"status": "Recording already in progress"}), 400

    filename = 'video.h264'  # Cambia a la ruta de archivo preferida
    duration = 10  # Duración en segundos, cámbialo según sea necesario

    recording_thread = Thread(target=record_video, args=(filename, duration))
    recording_thread.start()

    return jsonify({"status": "Recording started", "filename": filename})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    global recording

    if not recording:
        return jsonify({"status": "No recording in progress"}), 400

    recording = False
    if recording_thread is not None:
        recording_thread.join()

    return jsonify({"status": "Recording stopped"})

@app.route('/download_video')
def download_video():
    filename = 'video.h264'  # Cambia a la ruta de archivo preferida
    if os.path.exists(filename):
        return send_file(filename, as_attachment=True)
    else:
        return jsonify({"status": "File not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)