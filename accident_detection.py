import cv2

def detect_accident(video_path):

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("❌ Video not loaded")
        return False

    prev_frame = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if prev_frame is None:
            prev_frame = gray
            continue

        frame_diff = cv2.absdiff(prev_frame, gray)
        _, thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour)

            print("Contour area:", area)

            # 🚨 Adjust this value based on your video
            if area > 15000:
                print("🚨 Accident detected!")
                cap.release()
                return True

        prev_frame = gray

    cap.release()
    print("ℹ️ No accident detected")
    return False