import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import os
import base64
import requests
import logging

# Set up logging to log to a file and to the console
logging.basicConfig(filename='dataset_generator.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class VideoTransformer(VideoTransformerBase):
    def __init__(self):
        self.captured_frame = None
        self.capture_flag = False

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        if self.capture_flag:
            self.captured_frame = img
            self.capture_flag = False
        return img

    def capture_image(self):
        self.capture_flag = True


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
            file_sha = response.json().get('sha')
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
            return True
        else:
            logging.error(f"Failed to upload {repo_path}: {response.json()}")
            return False

    except Exception as e:
        logging.error(f"Error uploading file: {e}")
        return False


def main():
    st.title("Face Dataset Generator")
    st.markdown("""
        **Steps:**
        1. Enter Roll Number and Name.
        2. Use the webcam feed to capture images.
        3. Upload captured images to GitHub.
    """)

    # Input fields for metadata
    roll_number = st.text_input("Enter Roll Number", key="roll_number")
    name = st.text_input("Enter Student Name", key="student_name")
    repo = st.secrets.get("Repo")
    branch = st.secrets.get("Branch")
    token = st.secrets.get("TOKEN")

    # Directory to store temporary images
    temp_path = "/tmp/captured_images"
    os.makedirs(temp_path, exist_ok=True)

    # Initialize video transformer
    if "video_transformer" not in st.session_state:
        st.session_state["video_transformer"] = VideoTransformer()

    # WebRTC streamer
    webrtc_ctx = webrtc_streamer(
        key="example",
        video_transformer_factory=lambda: st.session_state["video_transformer"],
        media_stream_constraints={"video": True, "audio": False},
    )

    # Capture image functionality
    if st.button("Capture Image"):
        if not roll_number or not name:
            st.error("Please provide Roll Number and Name.")
            return

        if webrtc_ctx.video_transformer:
            webrtc_ctx.video_transformer.capture_image()
            if webrtc_ctx.video_transformer.captured_frame is not None:
                image_name = f"{roll_number}_{len(os.listdir(temp_path)) + 1}.jpg"
                image_path = os.path.join(temp_path, image_name)
                cv2.imwrite(image_path, webrtc_ctx.video_transformer.captured_frame)
                st.image(webrtc_ctx.video_transformer.captured_frame, caption="Captured Image")
                st.success(f"Image saved: {image_path}")
            else:
                st.error("No image captured. Try again!")

    # Upload images to GitHub
    if st.button("Upload Images"):
        if not roll_number or not repo or not branch or not token:
            st.error("Please fill in all required fields.")
            return

        uploaded_files = 0
        for file_name in os.listdir(temp_path):
            file_path = os.path.join(temp_path, file_name)
            repo_path = f"{roll_number}/{file_name}"
            if upload_to_github(file_path, repo, branch, token, repo_path):
                os.remove(file_path)
                uploaded_files += 1

        if uploaded_files > 0:
            st.success(f"Uploaded {uploaded_files} images to GitHub successfully!")
        else:
            st.error("No images uploaded. Check logs for details.")

    # Clear temporary directory
    if st.button("Clear Captured Images"):
        for file_name in os.listdir(temp_path):
            os.remove(os.path.join(temp_path, file_name))
        st.success("Cleared all captured images.")

    # Cleanup temporary directory after the session
    if st.button("Cleanup Temporary Directory"):
        try:
            os.rmdir(temp_path)
            st.success("Temporary directory cleaned up!")
        except Exception as e:
            st.warning(f"Error cleaning up temporary directory: {e}")


if __name__ == "__main__":
    main()
