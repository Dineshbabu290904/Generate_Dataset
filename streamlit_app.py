import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import numpy as np
import os
import base64
import requests
import logging

# Set up logging to log to a file and to the console
logging.basicConfig(filename='dataset_generator.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class VideoTransformer(VideoTransformerBase):
    def __init__(self):
        self.image_captured = False
        self.captured_frame = None

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")

        if self.image_captured:
            self.captured_frame = img
            self.image_captured = False

        return img

    def capture_image(self):
        self.image_captured = True


def upload_to_github(file_path, repo, branch, token, repo_path):
    """
    Uploads a single file to GitHub.
    """
    try:
        url = f'https://api.github.com/repos/{repo}/contents/{repo_path}'
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }

        with open(file_path, 'rb') as file:
            content = file.read()
        encoded_content = base64.b64encode(content).decode('utf-8')

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            file_sha = response.json()['sha']
            data = {
                'message': f'Update {repo_path}',
                'content': encoded_content,
                'branch': branch,
                'sha': file_sha
            }
        else:
            data = {
                'message': f'Add {repo_path}',
                'content': encoded_content,
                'branch': branch
            }

        response = requests.put(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            logging.info(f"Successfully uploaded {repo_path}")
        else:
            logging.error(f"Failed to upload {repo_path}: {response.json()}")

    except Exception as e:
        logging.error(f"Error uploading file: {e}")


def main():
    st.title("Face Dataset Generator")

    roll_number = st.text_input("Enter Roll Number")
    name = st.text_input("Enter Student Name")
    repo = st.secrets["Repo"]
    branch = st.secrets["Branch"]
    token = st.secrets["TOKEN"]

    temp_path = "/tmp/captured_images"
    os.makedirs(temp_path, exist_ok=True)

    if "video_transformer" not in st.session_state:
        st.session_state["video_transformer"] = VideoTransformer()

    webrtc_ctx = webrtc_streamer(
        key="example",
        video_transformer_factory=lambda: st.session_state["video_transformer"],
        media_stream_constraints={"video": True, "audio": False},
    )

    if st.button("Capture Image"):
        if webrtc_ctx.video_transformer:
            webrtc_ctx.video_transformer.capture_image()
            if webrtc_ctx.video_transformer.captured_frame is not None:
                image_path = os.path.join(temp_path, f"{roll_number}_{len(os.listdir(temp_path))}.jpg")
                cv2.imwrite(image_path, webrtc_ctx.video_transformer.captured_frame)
                st.image(webrtc_ctx.video_transformer.captured_frame, caption="Captured Image")
                st.success(f"Image saved to {image_path}")
            else:
                st.error("No image captured yet. Try again!")

    if st.button("Upload Images"):
        if not roll_number or not name or not repo or not branch or not token:
            st.error("Please enter all required fields.")
            return

        try:
            for file_name in os.listdir(temp_path):
                file_path = os.path.join(temp_path, file_name)
                repo_path = f"{roll_number}/{file_name}"
                upload_to_github(file_path, repo, branch, token, repo_path)
                os.remove(file_path)
            st.success("All images uploaded successfully!")
        except Exception as e:
            st.error(f"Error during upload: {e}")

    if st.button("Clear Captured Images"):
        for file_name in os.listdir(temp_path):
            os.remove(os.path.join(temp_path, file_name))
        st.success("Cleared all captured images.")

    os.rmdir(temp_path)


if __name__ == "__main__":
    main()
